# OnBase Pod Confluence action

This action takes in the two specific inputs, gathers the necessary variable information, and updates a Confluence document to reflect the up to date variable input list for the OnBase Pods. This action is specifically catered to the OnBase Pod repository and its corresponding Confluence page.

## Inputs

## `variables`

**Required** The text of the OnBase Pod Variable.tf file.

## `readme`

**Required** The text of the OnBase Pod README.md file.

## Example usage

uses: jalexaacobs/onbase-pod-confluence-action@main
with:
    variables: 'This text comes from the variables.tf file'
    readme: 'This text comes from the README.md file'