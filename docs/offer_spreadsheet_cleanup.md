# Spreadsheet Cleanup Service

## The Problem
Many small businesses, agencies, and independent professionals struggle with messy data in Excel spreadsheets. Whether it's contact lists with inconsistent phone numbers, leads with malformed email addresses, or just general messy formatting, cleaning up spreadsheets manually takes hours. 

## The Offer
Courier offers an automated **Spreadsheet Cleanup Service** for a flat fee of €49. 

We will:
1. Normalize and validate all email addresses.
2. Format all phone numbers to a consistent international format.
3. Clean up capitalization on names and addresses.
4. Deduplicate rows based on your specified primary key.

## Why Courier?
We use the `courier_runtime.workbook` standard library to ensure **absolute data integrity**.
Our cleanup operates exclusively on values. Your formulas, macros, charts, and cell styles are preserved byte-for-byte. We perform an atomic replacement and generate a receipt of exact mutations made. 

## Guarantee
If we cannot parse or successfully clean your spreadsheet without losing data, you pay nothing. The file never leaves our secure pipeline and is deleted immediately after delivery.

## Sample 
See our automated capability using `courier_runtime.workbook` in `scripts/revenue_workbook_sample.py`.
