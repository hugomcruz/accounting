# Introduction
The objective of this project is creating a light accounting software for companies.


# High Level Technical Details
- Front-end UI in React
- Backend in Python
- Storage for Data: PostgreSQL Databae
- Storage for Files: S3 or compatible. 

# Features
- Multi Person Login with Roles
- Single tenant for this release supporting only 1 company per instance. 
- Dashboard with the consolidated company financials: profit and loss and results, calculated in real time. 
- Invoice processing: upload invoice, detect QR code for the portuguese tax system and fill in the relevant fields imediatelly. 
- SAFT Import, with focus on the invoices issued. 
- Bank Statements processing: load bank file and store the data. 
- Reconciliation module to link bank statements with invoices automatically and also employee payments, tax payments...
- Tax module to load the Tax payment files sent by the accounting. These are PDF. 
- Employees: Employee list, contacts. 
- Companies: Companies with which we do business. When an invoice is loaded if the Tax ID does not exist, a new company should be created. 
- Payroll: Load the payroll documents and tag them to an employee.


# Feature Modules Description

## Multi Person Login with Roles
Create a user management module.
- Credentials authentication is based on the Postgres Database on the first release. 

User Parameters:
- First Name
- Family Name
- Full Name
- Phone
- Username
- Password
- Role: Admin, Finance, Accounting

## Company Dashboard
The fiscal years are calendar years and the system must support multiple fiscal years. 
On the dashboard, you must show:
- Financial summary
Must be a table with:
- Previous and current year
- Total Revenue, Total Expenses and Net Profit
The current year must have always year to date. 

## The invoice processing
The invoices must be uploaded in bulk. It must have the possibility of uploading more than 1 invoice. 
The invoice section must have 3 menu options: UPload invoices, Review loaded invoices and View Invoices

When the invoices are uploaded:
- The system must store the invoices locally and on S3
- Success is only returned to the user when all the invoices are on S3 and in the local filesystem. 
- Each invoice must also be inserted in a queue in the database with the link to the local file and the S3 file

Then, an upload should signal a processing invoice function that:
- Scan the QR code from the PT Tax department and create the invoice on the invoices table with the details:
    Supplier NIPC
    Invoice Number
    Date
    Total AMount
    Customer NIPC
    Tax Amount - Vat 6%, Vat 23% Separated if possible
    ATCUD
    S3 file location
    Foreign currency invoice flag
    Foreign currency
    Original total amount
    Original Tax amount
    Currency exchange
- If the supplier company does not exist create it on the companies table. 
- If you cannot read the invoice QR to determine at least the fields above, then put the invoice in a queue in the menu "Review Loaded Invoices" and delete the local file. 
- In this menu, show a list of the invoices pending processing. When an invoice is selected, open the image of the invoice on the left frame and on the right the details than need to be filled in manually. 
Once submited, the invoice details are added to the invoice table and the invoice is deleted from this processing queue. 




## SAFT Import
This file contains all the invoices, credit notes and receipts. 
Load of these from the SAFT file and these invoices represent the company revenue. 
Load also the receipts to match with the invoices. 
Load the credit notes if exist, as these are usually used to return money or create a credit for the customer. 


## Employees
Create a menu section to manage employees
Create the fiels you deem necessary to record and employee data. 
Add on fields
    NIF
    Social Security Number

## Payroll
In the payroll menu, we are not calculating the amounts to be paid. 
We receive the salary receitps and we load them here for each employee.
In the first phase after loading the PDF we will need to record the data. 
    Total AMount
    NEtAmount
    SocialSecurity deduction
    Income tax deduction
    Meal subsidy
Let's keep it simple for now. 
    

## Companies
Create a menu to manage companies we do business with. 
Key field in the DB is the NIPC. 
The add the usual fields for a company and we refine later. 





# Backend Asynchronous modules

Create a separate module to run on standalone mode, outside the main project. Code in Python as well. 

## Invoice from Email
- Module to read emails from outlook for business and retrieve the ones with attachment. 
- Process the file and search for a ATCUD QR code and if you detect one process it as an invoice loading described above. 
- Add the sender and create filters to identify this as an invoice sender. 

- If you cannot detect the QR store the invoice on a temporay S3 storage. 
- Create a UI with a queue of these invoices, and the email details to decide if this is to be processed. If the file is rejected, put in a blacklist to skip from then on. If it is approved, put the sender in a white list to process this invoice as above. 
- If it is approved add it to the processing queue of the invoices. 











