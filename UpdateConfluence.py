import os
import json
import requests
import re
import sys

# CONSTANTS
CONFLUENCE_TOKEN = os.environ['ATLASSIAN_TOKEN']
CONFLUENCE_PAGE = os.environ['CONFLUENCE_PAGE']
CONTENT_TYPE = "application/vnd.api+json"
CONF_URL = "https://hyland.atlassian.net/wiki/rest/api/content/"

# helper method that takes a relative filepath and dumps the passed in object to a file
def dumpToFile(fileName, data):
    with open(fileName, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# grabs the content body for the provided page name
def getPageBodyContent(title):
    headers = {
        'Authorization': 'Basic ' + CONFLUENCE_TOKEN,
        'Content-Type': 'application/json'
    }
        
    response = requests.request("GET", CONF_URL + f"?title={title}&type=page&expand=body.storage,metadata.properties,childTypes.all", headers=headers)
    print(response.status_code)
    
    body = json.loads(response.text)
    content = body["results"][0]["body"]["storage"]["value"] # get the body from the response
    id = body["results"][0]["id"] # get the ID

    return (id, content)

# takes in a markdown'd README file and extracts the input var contents
def extractReadmeInputs(readmeFileText, variablesInfo):

    print(variablesInfo)




    # lets find the text between the Inputs header and the Outputs header
    headersMatch = re.search(r"(## Inputs((\s|.)*?)## Outputs)", readmeFileText)
    inputsText = headersMatch.groups()[1]

    # lets get the headers now
    headersMatch = re.search(r"(\s*(\|\s*\w*\s*)*)", inputsText)
    headers = (headersMatch.groups()[0]).replace('|', '').split()

    # now lets get each variable
    vars = re.split(r"\|\s*<a\s*name=\"\w*\"></a>\s*\[",inputsText)
    vars.pop(0) # we dont want the first item in the list as its markdown meta info

    for var in vars:
        # lets split up based on the columns, name has to be handled differently as the first one
        varValues = re.split(r"\|", var)
        name = re.split(r"\]\(#",varValues[0])[0].replace('\\','') # getting it to the correct format
        print(name)
        # add the other attribute values to the json object
        for x in range(1,len(headers)):
            variablesInfo[name][headers[x]] = varValues[x].strip()

def updatePage(pageID, contentBody):
    headers = {
        'Authorization': 'Basic ' + CONFLUENCE_TOKEN,
        'Content-Type': 'application/json'
    }

    response = requests.request("GET", CONF_URL + pageID, headers=headers)
    data = json.loads(response.text)
    currentVersion = data["version"]["number"]
    print(currentVersion)
    payload = json.dumps({
        "type": "page",
        "title": "TEST OnBase Pod Terraform Inputs",
        "version": {
        "number": currentVersion + 1
        },
        "status": "current",
        "body": {
        "storage": {
            "value": contentBody,
            "representation": "storage"
        }
        }
    })

    print(payload)
    response = requests.request("PUT", CONF_URL + pageID, headers=headers, data=payload)
    print(response.status_code)

# Retrieves the Variables.tf file and returns the text
def grabVariablesFile():
    # fileText = ""
    # with open('./target_repository/variables.tf') as f:
    #     fileText = f.read()
    # return fileText
    print(os.environ['INPUT_VARIABLES'])
    return os.environ['INPUT_VARIABLES']

# Retrieves the README file and returns the text
def grabReadmeFile():
    # fileText = ""
    # with open('./target_repository/README.md') as f:
    #     fileText = f.read()
    # return fileText
    print(os.environ['INPUT_README'])
    return os.environ['INPUT_README']

# extracts useful info about all the variables in passed in variables file
# The following additional arguments (that we care about) are allowed on each var:
#     default 
#     type
#     description 
#     validation
#     sensitive
def extractVariableInfo(variablesFileText, readmeFileText):

    variablesInfo = {}

    # nasty regex, essentially matches each variable {} block in the file
    matches = re.split(r"(variable\s*\")", variablesFileText)
    matches.pop(0) # we dont care about the first one
    matches = matches[1::2] # we only want every other

    for match in matches:
        varInfo = {}

        # first get the names
        name = re.search(r"(.*?)\s*\"", match).groups()[0]

        # then check for validation and sensitve attributes from the variables.tf file passed in

        # validation
        valMatch = re.search(r"validation\s*\{\s*", match)
        if valMatch:
            # there is a validation block, lets grab the condition/error message
            # it will contain a condition and a error_message attribute, just grab both in whatever order
            condOrErrorMatch = re.search(r"(condition|error_message)\s*=\s*(.*)\s*(condition|error_message)\s*=\s*(.*)", match)
            conditionOrError = condOrErrorMatch.groups()[0]
            conditionOrErrorValue = condOrErrorMatch.groups()[1]
            conditionOrError2 = condOrErrorMatch.groups()[2]
            conditionOrErrorValue2 = condOrErrorMatch.groups()[3]
            varInfo["Validation"] = {
                conditionOrError : conditionOrErrorValue,
                conditionOrError2 : conditionOrErrorValue2
            }
        else:
            varInfo["Validation"] = None

        # sensitive
        sensMatch = re.search(r"sensitive(\s*)=(\s*)(true)", match)
        if sensMatch:
            varInfo["Sensitive"] = sensMatch.groups()[2]
        else:
            varInfo["Sensitive"] = None

        variablesInfo[name] = varInfo

    extractReadmeInputs(readmeFileText, variablesInfo)

    return variablesInfo

def formatTableForConfluence(variables, confluenceValues):
    # handle each row
    formatString = ""
    for variable, info in variables.items():

        # handle validation
        validationString = None
        if info["Validation"]:
            validationString = f'Must satisfy the following condition:\n\n{info["Validation"]["condition"]}'

        CPEOB_Notes = ""
        cp_notes = ""
        cp_display = ""

        # handle the 3 rows with manual input, we want to save any values in those columns so they dont get overwritten
        if variable in confluenceValues:
            CPEOB_Notes = confluenceValues[variable]['CPEOB_Notes']
            cp_notes = confluenceValues[variable]['CP_Notes']
            cp_display = confluenceValues[variable]['CP_Display']

        # format the row
        formatString = formatString + f'''
            <tr>
              <td>{variable}</td>
              <td>{info["Required"]}</td>
              <td>{info["Type"].replace('`','')}</td>
              <td>{info["Default"].replace('`','')}</td>
              <td>{validationString}</td>
              <td>{info["Sensitive"]}</td>
              <td>{info["Description"]}</td>
              <td>{CPEOB_Notes}</td>
              <td>{cp_notes}</td>
              <td>{cp_display}</td>
            </tr>
        '''
    return formatString

def formatConfluence(variables, confluenceValues):
    # start the table
    contentString = "<table data-layout=\"full-width\" ac:local-id=\"91cfb662-2b44-4047-a7bb-dcfa0139de88\"><tbody><tr><th><p><span style=\"color: rgb(0,0,0);\">variable</span></p></th><th><p><span style=\"color: rgb(0,0,0);\">required</span></p></th><th><p><span style=\"color: rgb(0,0,0);\">type</span></p></th><th><p>default</p></th><th><p><span style=\"color: rgb(0,0,0);\">validation</span></p></th><th><p><span style=\"color: rgb(0,0,0);\">secret</span></p></th><th><p>description</p></th><th><p>CPEOB Additional Notes</p></th><th><p>Control Plane Notes</p></th><th><p>CP Display</p></th></tr>"

    tableContentString = formatTableForConfluence(variables, confluenceValues)
    contentString = contentString + tableContentString

    # end the table
    contentString = contentString + "</tbody></table>"
    return contentString

# retrieves the tables values for the exiting confluence doc
def getExistingConfluenceInfo():
    # grab the existing body content
    pageId, content = getPageBodyContent(CONFLUENCE_PAGE)

    # grab and save everything before the first table
    tablePrefix = re.search(r"((.|\s)*?)<table", content).groups()[0]

    confluenceValues = {}

    # lets extract the values
    rows = re.findall(r"(<tr>(.|\s)*?<\/tr>)", content)
    rows.pop(0) # we dont care about the first row
    for row in rows:
        # we want all column values to fill the json object
        columnValues = re.findall(r"<td>((.|\s)*?)<\/td>", row[0])

        name = columnValues[0][0].replace('<p>','').replace('</p>','') # need to strip away <p></p> formatting that gets inserted
        required = columnValues[1][0]
        type = columnValues[2][0]
        default = columnValues[3][0]
        validation = columnValues[4][0]
        secret = columnValues[5][0]
        description = columnValues[6][0]
        cpeob_notes = columnValues[7][0]
        cp_notes = columnValues[8][0]
        cp_display = columnValues[9][0]

        confluenceValues[name] = {
            'Required' : required,
            'Type' : type,
            'Default' : default,
            'Validation' : validation,
            'Secret' : secret,
            'Description' : description,
            'CPEOB_Notes' : cpeob_notes,
            'CP_Notes' : cp_notes,
            'CP_Display' : cp_display
        }

    return (pageId, tablePrefix, confluenceValues)

pageId, tablePrefix, confluenceValues = getExistingConfluenceInfo()

# work towards getting the vars from README and variables.tf
variablesFileText = grabVariablesFile()
readmeFileText = grabReadmeFile()

# lets extract each variable with its useful info
variables = extractVariableInfo(variablesFileText, readmeFileText) 

# lets make our own table 
content = tablePrefix + formatConfluence(variables, confluenceValues)

# weird error where the <br> tags need to be closed or the request will fail
content = content.replace('<br>','<br/>')

updatePage(pageId, content)
