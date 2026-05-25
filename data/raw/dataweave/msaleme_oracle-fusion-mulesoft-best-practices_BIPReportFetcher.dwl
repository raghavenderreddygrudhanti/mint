%dw 2.0

/**
 * Oracle Fusion BIP (Business Intelligence Publisher) Report Fetcher Module
 * 
 * This module provides comprehensive utilities for fetching and processing 
 * BIP reports from Oracle Fusion Cloud EPM and ERP modules.
 * 
 * Features:
 * - SOAP-based report requests
 * - Asynchronous and synchronous report execution
 * - Multiple output formats (XML, JSON, CSV, PDF, Excel)
 * - Base64 decoding and content transformation
 * - Report scheduling and batch processing
 * - Parameter validation and formatting
 * 
 * Author: Oracle Fusion + MuleSoft Integration Team
 * Version: 1.0.0
 * Last Modified: 2024-06-24
 */

// Import required libraries
import * from dw::core::Strings
import * from dw::core::Arrays
import fromBase64 from dw::core::Binaries
import toBase64 from dw::core::Binaries

/**
 * Builds SOAP envelope for BIP report execution
 * @param reportRequest - Report request parameters
 * @return SOAP envelope as string
 */
fun buildReportSOAPRequest(reportRequest: Object): String = do {
    var reportPath = reportRequest.reportPath
    var reportParameters = reportRequest.parameters default {}
    var outputFormat = reportRequest.outputFormat default "JSON"
    var locale = reportRequest.locale default "en-US"
    
    var parametersXML = reportParameters pluck ((value, key) -> 
        "<ns2:listOfParamNameValues>
            <ns2:item>
                <ns2:name>$(key)</ns2:name>
                <ns2:values>
                    <ns2:item>$(value)</ns2:item>
                </ns2:values>
            </ns2:item>
        </ns2:listOfParamNameValues>"
    ) joinBy ""
    
    ---
    '<?xml version="1.0" encoding="UTF-8"?>
    <soap:Envelope 
        xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
        xmlns:pub="http://xmlns.oracle.com/oxp/service/PublicReportService">
        <soap:Header>
            <wsse:Security 
                xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
                soap:mustUnderstand="1">
                <wsse:UsernameToken>
                    <wsse:Username>$(reportRequest.username)</wsse:Username>
                    <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">$(reportRequest.password)</wsse:Password>
                </wsse:UsernameToken>
            </wsse:Security>
        </soap:Header>
        <soap:Body>
            <pub:runReport>
                <pub:reportRequest>
                    <pub:attributeFormat>$(outputFormat)</pub:attributeFormat>
                    <pub:attributeLocale>$(locale)</pub:attributeLocale>
                    <pub:reportAbsolutePath>$(reportPath)</pub:reportAbsolutePath>
                    $(parametersXML)
                </pub:reportRequest>
            </pub:runReport>
        </soap:Body>
    </soap:Envelope>'
}

/**
 * Builds async SOAP request for large reports
 * @param reportRequest - Report request parameters
 * @return SOAP envelope for async execution
 */
fun buildAsyncReportSOAPRequest(reportRequest: Object): String = do {
    var reportPath = reportRequest.reportPath
    var reportParameters = reportRequest.parameters default {}
    var outputFormat = reportRequest.outputFormat default "JSON"
    var deliveryChannel = reportRequest.deliveryChannel default "FILE"
    
    var parametersXML = reportParameters pluck ((value, key) -> 
        "<ns2:listOfParamNameValues>
            <ns2:item>
                <ns2:name>$(key)</ns2:name>
                <ns2:values>
                    <ns2:item>$(value)</ns2:item>
                </ns2:values>
            </ns2:item>
        </ns2:listOfParamNameValues>"
    ) joinBy ""
    
    ---
    '<?xml version="1.0" encoding="UTF-8"?>
    <soap:Envelope 
        xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
        xmlns:pub="http://xmlns.oracle.com/oxp/service/PublicReportService">
        <soap:Header>
            <wsse:Security 
                xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
                soap:mustUnderstand="1">
                <wsse:UsernameToken>
                    <wsse:Username>$(reportRequest.username)</wsse:Username>
                    <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">$(reportRequest.password)</wsse:Password>
                </wsse:UsernameToken>
            </wsse:Security>
        </soap:Header>
        <soap:Body>
            <pub:scheduleReport>
                <pub:scheduleRequest>
                    <pub:reportRequest>
                        <pub:attributeFormat>$(outputFormat)</pub:attributeFormat>
                        <pub:attributeLocale>$(reportRequest.locale default "en-US")</pub:attributeLocale>
                        <pub:reportAbsolutePath>$(reportPath)</pub:reportAbsolutePath>
                        $(parametersXML)
                    </pub:reportRequest>
                    <pub:schedule>
                        <pub:startDate>$(now() as String {format: "yyyy-MM-dd'T'HH:mm:ss"})</pub:startDate>
                        <pub:frequency>ONCE</pub:frequency>
                    </pub:schedule>
                    <pub:deliveryRequest>
                        <pub:deliveryChannel>$(deliveryChannel)</pub:deliveryChannel>
                    </pub:deliveryRequest>
                </pub:scheduleRequest>
            </pub:scheduleReport>
        </soap:Body>
    </soap:Envelope>'
}

/**
 * Parses SOAP response and extracts report data
 * @param soapResponse - SOAP response from BIP service
 * @return Parsed report data
 */
fun parseReportSOAPResponse(soapResponse: String): Object = do {
    // This is a simplified parser - in real implementation you'd use proper XML parsing
    var reportBytes = soapResponse match {
        case contains $ "reportBytes" -> 
            (soapResponse splitBy "<pub:reportBytes>")[1] splitBy "</pub:reportBytes>" then $[0]
        else -> null
    }
    
    var reportContentType = soapResponse match {
        case contains $ "reportContentType" -> 
            (soapResponse splitBy "<pub:reportContentType>")[1] splitBy "</pub:reportContentType>" then $[0]
        else -> "application/octet-stream"
    }
    
    ---
    {
        reportBytes: reportBytes,
        contentType: reportContentType,
        isSuccess: reportBytes != null,
        timestamp: now() as String {format: "yyyy-MM-dd'T'HH:mm:ss'Z'"}
    }
}

/**
 * Decodes base64 report content to specified format
 * @param reportResponse - Report response with base64 content
 * @param targetFormat - Target format for transformation
 * @return Decoded and transformed report data
 */
fun decodeReportContent(reportResponse: Object, targetFormat: String = "JSON"): Object = do {
    var decodedContent = if (reportResponse.reportBytes != null)
        fromBase64(reportResponse.reportBytes) as String
    else null
    
    var transformedContent = if (decodedContent != null)
        targetFormat match {
            case "JSON" -> 
                try {
                    decodedContent as Object
                } catch (e) {
                    { rawContent: decodedContent, parseError: e.message }
                }
            case "CSV" -> 
                parseCSVContent(decodedContent)
            case "XML" -> 
                try {
                    decodedContent as Object {reader: "application/xml"}
                } catch (e) {
                    { rawContent: decodedContent, parseError: e.message }
                }
            else -> decodedContent
        }
    else null
    
    ---
    {
        content: transformedContent,
        rawContent: decodedContent,
        format: targetFormat,
        contentType: reportResponse.contentType,
        size: if (decodedContent != null) sizeOf(decodedContent) else 0,
        isDecoded: decodedContent != null
    }
}

/**
 * Parses CSV content into structured data
 * @param csvContent - CSV content as string
 * @return Structured data array
 */
fun parseCSVContent(csvContent: String): Array = do {
    var lines = csvContent splitBy "\n"
    var headers = if (!isEmpty(lines)) 
        (lines[0] splitBy ",") map trim($)
    else []
    
    var dataRows = if (sizeOf(lines) > 1)
        lines[1 to -1] filter (!isEmpty(trim($))) 
        map ((row) -> 
            (row splitBy ",") map trim($)
        )
    else []
    
    ---
    dataRows map ((row, index) -> 
        headers reduce ((header, acc = {}, headerIndex) -> 
            acc ++ {
                (header): row[headerIndex] default ""
            }
        )
    )
}

/**
 * Validates report request parameters
 * @param reportRequest - Report request to validate
 * @return Validation result
 */
fun validateReportRequest(reportRequest: Object): Object = do {
    var errors = []
    
    var pathError = if (isEmpty(reportRequest.reportPath default ""))
        ["reportPath is required"]
    else []
    
    var formatError = if (!isEmpty(reportRequest.outputFormat default "") and 
                         !contains(["JSON", "XML", "CSV", "PDF", "EXCEL"], reportRequest.outputFormat))
        ["outputFormat must be one of: JSON, XML, CSV, PDF, EXCEL"]
    else []
    
    var credentialsError = if (isEmpty(reportRequest.username default "") or 
                              isEmpty(reportRequest.password default ""))
        ["username and password are required"]
    else []
    
    var allErrors = errors ++ pathError ++ formatError ++ credentialsError
    ---
    {
        isValid: isEmpty(allErrors),
        errors: allErrors
    }
}

/**
 * Builds report catalog request
 * @param catalogRequest - Catalog request parameters
 * @return SOAP envelope for catalog request
 */
fun buildCatalogSOAPRequest(catalogRequest: Object): String = do {
    var folderPath = catalogRequest.folderPath default "/"
    
    ---
    '<?xml version="1.0" encoding="UTF-8"?>
    <soap:Envelope 
        xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
        xmlns:pub="http://xmlns.oracle.com/oxp/service/PublicReportService">
        <soap:Header>
            <wsse:Security 
                xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
                soap:mustUnderstand="1">
                <wsse:UsernameToken>
                    <wsse:Username>$(catalogRequest.username)</wsse:Username>
                    <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">$(catalogRequest.password)</wsse:Password>
                </wsse:UsernameToken>
            </wsse:Security>
        </soap:Header>
        <soap:Body>
            <pub:getFolderContents>
                <pub:folderAbsolutePath>$(folderPath)</pub:folderAbsolutePath>
            </pub:getFolderContents>
        </soap:Body>
    </soap:Envelope>'
}

/**
 * Builds job status check request
 * @param jobRequest - Job status request parameters
 * @return SOAP envelope for job status check
 */
fun buildJobStatusSOAPRequest(jobRequest: Object): String = do {
    var jobId = jobRequest.jobId
    
    ---
    '<?xml version="1.0" encoding="UTF-8"?>
    <soap:Envelope 
        xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
        xmlns:pub="http://xmlns.oracle.com/oxp/service/PublicReportService">
        <soap:Header>
            <wsse:Security 
                xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
                soap:mustUnderstand="1">
                <wsse:UsernameToken>
                    <wsse:Username>$(jobRequest.username)</wsse:Username>
                    <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">$(jobRequest.password)</wsse:Password>
                </wsse:UsernameToken>
            </wsse:Security>
        </soap:Header>
        <soap:Body>
            <pub:getScheduleReportJobInfo>
                <pub:jobID>$(jobId)</pub:jobID>
            </pub:getScheduleReportJobInfo>
        </soap:Body>
    </soap:Envelope>'
}

/**
 * Parses job status response
 * @param statusResponse - SOAP response with job status
 * @return Parsed job status information
 */
fun parseJobStatusResponse(statusResponse: String): Object = do {
    var jobStatus = statusResponse match {
        case contains $ "jobStatus" -> 
            (statusResponse splitBy "<pub:jobStatus>")[1] splitBy "</pub:jobStatus>" then $[0]
        else -> "UNKNOWN"
    }
    
    var isCompleted = contains(["SUCCEEDED", "FAILED", "CANCELLED"], jobStatus)
    var isSuccessful = jobStatus == "SUCCEEDED"
    
    ---
    {
        jobStatus: jobStatus,
        isCompleted: isCompleted,
        isSuccessful: isSuccessful,
        canRetry: jobStatus == "FAILED",
        timestamp: now() as String {format: "yyyy-MM-dd'T'HH:mm:ss'Z'"}
    }
}

/**
 * Formats report parameters for different data types
 * @param parameters - Raw parameters object
 * @return Formatted parameters suitable for BIP
 */
fun formatReportParameters(parameters: Object): Object = 
    parameters mapObject ((value, key) -> {
        (key): value match {
            case is String -> value
            case is Number -> value as String
            case is Boolean -> if (value) "true" else "false"
            case is Date -> value as String {format: "yyyy-MM-dd"}
            case is DateTime -> value as String {format: "yyyy-MM-dd'T'HH:mm:ss"}
            else -> value as String
        }
    })

/**
 * Builds report parameter validation rules
 * @param reportPath - Path to the report
 * @return Parameter validation rules based on report type
 */
fun getReportParameterRules(reportPath: String): Object = 
    reportPath match {
        case contains $ "Financial" -> {
            requiredParams: ["period", "ledger"],
            optionalParams: ["department", "account"],
            dateParams: ["fromDate", "toDate"],
            numericParams: ["amount", "threshold"]
        }
        case contains $ "Payroll" -> {
            requiredParams: ["payPeriod", "businessUnit"],
            optionalParams: ["employee", "department"],
            dateParams: ["payDate", "hireDate"],
            numericParams: ["salary", "hours"]
        }
        case contains $ "Procurement" -> {
            requiredParams: ["supplier", "category"],
            optionalParams: ["buyer", "approver"],
            dateParams: ["orderDate", "deliveryDate"],
            numericParams: ["amount", "quantity"]
        }
        else -> {
            requiredParams: [],
            optionalParams: [],
            dateParams: [],
            numericParams: []
        }
    }

/**
 * Validates report parameters against rules
 * @param parameters - Parameters to validate
 * @param reportPath - Report path for rule lookup
 * @return Validation result with specific errors
 */
fun validateReportParameters(parameters: Object, reportPath: String): Object = do {
    var rules = getReportParameterRules(reportPath)
    var errors = []
    
    var missingRequired = rules.requiredParams filter (param -> 
        isEmpty(parameters[param] default "")
    ) map ("Missing required parameter: " ++ $)
    
    var invalidDates = rules.dateParams filter (param -> 
        parameters[param] != null and 
        try { parameters[param] as Date; false } catch (e) { true }
    ) map ("Invalid date format for parameter: " ++ $)
    
    var invalidNumbers = rules.numericParams filter (param -> 
        parameters[param] != null and 
        try { parameters[param] as Number; false } catch (e) { true }
    ) map ("Invalid number format for parameter: " ++ $)
    
    var allErrors = errors ++ missingRequired ++ invalidDates ++ invalidNumbers
    ---
    {
        isValid: isEmpty(allErrors),
        errors: allErrors,
        parameterRules: rules
    }
}

/**
 * Handles BIP service errors and provides meaningful messages
 * @param errorResponse - Error response from BIP service
 * @return Standardized error information
 */
fun handleBIPError(errorResponse: Object): Object = {
    errorCode: errorResponse.faultcode default "BIP_ERROR",
    errorMessage: errorResponse.faultstring default "BIP service error occurred",
    details: errorResponse.detail default {},
    timestamp: now() as String {format: "yyyy-MM-dd'T'HH:mm:ss'Z'"},
    retryable: contains(errorResponse.faultstring default "", "timeout") or 
               contains(errorResponse.faultstring default "", "unavailable"),
    httpStatus: 500
}