%dw 2.0

/**
 * Oracle Fusion Error Mapping Module
 * 
 * This module provides comprehensive error handling and mapping utilities for 
 * Oracle Fusion Cloud integrations. It standardizes error responses across 
 * different Oracle services and provides consistent error handling patterns.
 * 
 * Features:
 * - Standardized error response format
 * - Oracle-specific error code mapping
 * - HTTP status code normalization
 * - Retry logic recommendations
 * - Error categorization and severity levels
 * - Detailed error context preservation
 * 
 * Author: Oracle Fusion + MuleSoft Integration Team
 * Version: 1.0.0
 * Last Modified: 2024-06-24
 */

// Import required libraries
import * from dw::core::Strings
import * from dw::core::Arrays

/**
 * Maps Oracle Fusion REST API errors to standardized format
 * @param oracleError - Error response from Oracle Fusion REST API
 * @return Standardized error object
 */
fun mapFusionRESTError(oracleError: Object): Object = do {
    var errorCode = oracleError.errorCode default oracleError.code default "FUSION_ERROR"
    var errorMessage = oracleError.errorMessage default oracleError.message default "Oracle Fusion error occurred"
    var errorDetails = oracleError.errorDetails default oracleError.details default []
    
    var mappedError = errorCode match {
        case "INVALID_VALUE" -> {
            category: "VALIDATION_ERROR",
            severity: "ERROR",
            httpStatus: 400,
            retryable: false,
            userMessage: "Invalid input value provided"
        }
        case "MISSING_REQUIRED_FIELD" -> {
            category: "VALIDATION_ERROR", 
            severity: "ERROR",
            httpStatus: 400,
            retryable: false,
            userMessage: "Required field is missing"
        }
        case "DUPLICATE_VALUE" -> {
            category: "BUSINESS_ERROR",
            severity: "ERROR", 
            httpStatus: 409,
            retryable: false,
            userMessage: "Duplicate value not allowed"
        }
        case "INSUFFICIENT_PRIVILEGES" -> {
            category: "SECURITY_ERROR",
            severity: "ERROR",
            httpStatus: 403,
            retryable: false,
            userMessage: "Insufficient privileges to perform operation"
        }
        case "INVALID_CREDENTIALS" -> {
            category: "AUTHENTICATION_ERROR",
            severity: "ERROR",
            httpStatus: 401,
            retryable: false,
            userMessage: "Invalid authentication credentials"
        }
        case "SERVICE_UNAVAILABLE" -> {
            category: "SYSTEM_ERROR",
            severity: "ERROR",
            httpStatus: 503,
            retryable: true,
            userMessage: "Oracle Fusion service temporarily unavailable"
        }
        case "TIMEOUT" -> {
            category: "SYSTEM_ERROR",
            severity: "WARNING",
            httpStatus: 504,
            retryable: true,
            userMessage: "Request timeout occurred"
        }
        else -> {
            category: "UNKNOWN_ERROR",
            severity: "ERROR",
            httpStatus: 500,
            retryable: true,
            userMessage: "An unexpected error occurred"
        }
    }
    
    ---
    {
        errorCode: errorCode,
        errorMessage: errorMessage,
        category: mappedError.category,
        severity: mappedError.severity,
        httpStatus: mappedError.httpStatus,
        retryable: mappedError.retryable,
        userMessage: mappedError.userMessage,
        details: errorDetails,
        timestamp: now() as String {format: "yyyy-MM-dd'T'HH:mm:ss'Z'"},
        source: "ORACLE_FUSION_REST"
    }
}

/**
 * Maps Oracle Fusion SOAP/BIP errors to standardized format
 * @param soapError - Error response from Oracle SOAP/BIP service
 * @return Standardized error object
 */
fun mapFusionSOAPError(soapError: Object): Object = do {
    var faultCode = soapError.faultcode default "SOAP_FAULT"
    var faultString = soapError.faultstring default "SOAP service error"
    var faultDetail = soapError.detail default {}
    
    var mappedError = faultCode match {
        case "soap:Client" -> {
            category: "CLIENT_ERROR",
            severity: "ERROR",
            httpStatus: 400,
            retryable: false,
            userMessage: "Invalid request sent to Oracle service"
        }
        case "soap:Server" -> {
            category: "SERVER_ERROR",
            severity: "ERROR",
            httpStatus: 500,
            retryable: true,
            userMessage: "Oracle server encountered an error"
        }
        case "BIP-10001" -> {
            category: "REPORT_ERROR",
            severity: "ERROR",
            httpStatus: 404,
            retryable: false,
            userMessage: "Report not found or access denied"
        }
        case "BIP-10002" -> {
            category: "PARAMETER_ERROR",
            severity: "ERROR",
            httpStatus: 400,
            retryable: false,
            userMessage: "Invalid report parameters provided"
        }
        case "BIP-10003" -> {
            category: "EXECUTION_ERROR",
            severity: "ERROR",
            httpStatus: 500,
            retryable: true,
            userMessage: "Report execution failed"
        }
        case "ESS-00001" -> {
            category: "JOB_ERROR",
            severity: "ERROR",
            httpStatus: 500,
            retryable: true,
            userMessage: "ESS job execution failed"
        }
        else -> {
            category: "SOAP_ERROR",
            severity: "ERROR",
            httpStatus: 500,
            retryable: true,
            userMessage: "SOAP service error occurred"
        }
    }
    
    ---
    {
        errorCode: faultCode,
        errorMessage: faultString,
        category: mappedError.category,
        severity: mappedError.severity,
        httpStatus: mappedError.httpStatus,
        retryable: mappedError.retryable,
        userMessage: mappedError.userMessage,
        details: faultDetail,
        timestamp: now() as String {format: "yyyy-MM-dd'T'HH:mm:ss'Z'"},
        source: "ORACLE_FUSION_SOAP"
    }
}

/**
 * Maps HTTP connectivity errors to standardized format
 * @param httpError - HTTP connectivity error
 * @return Standardized error object
 */
fun mapHTTPError(httpError: Object): Object = do {
    var statusCode = httpError.statusCode default httpError.status default 500
    var errorMessage = httpError.message default httpError.reasonPhrase default "HTTP error occurred"
    
    var mappedError = statusCode match {
        case 400 -> {
            category: "BAD_REQUEST",
            severity: "ERROR",
            retryable: false,
            userMessage: "Invalid request format or parameters"
        }
        case 401 -> {
            category: "UNAUTHORIZED",
            severity: "ERROR", 
            retryable: false,
            userMessage: "Authentication required or failed"
        }
        case 403 -> {
            category: "FORBIDDEN",
            severity: "ERROR",
            retryable: false,
            userMessage: "Access forbidden - insufficient permissions"
        }
        case 404 -> {
            category: "NOT_FOUND",
            severity: "ERROR",
            retryable: false,
            userMessage: "Requested resource not found"
        }
        case 429 -> {
            category: "RATE_LIMITED",
            severity: "WARNING",
            retryable: true,
            userMessage: "Rate limit exceeded - please retry later"
        }
        case 500 -> {
            category: "INTERNAL_ERROR",
            severity: "ERROR",
            retryable: true,
            userMessage: "Internal server error occurred"
        }
        case 502 -> {
            category: "BAD_GATEWAY",
            severity: "ERROR",
            retryable: true,
            userMessage: "Bad gateway - upstream server error"
        }
        case 503 -> {
            category: "SERVICE_UNAVAILABLE",
            severity: "ERROR",
            retryable: true,
            userMessage: "Service temporarily unavailable"
        }
        case 504 -> {
            category: "GATEWAY_TIMEOUT",
            severity: "WARNING",
            retryable: true,
            userMessage: "Gateway timeout - request took too long"
        }
        else -> {
            category: "HTTP_ERROR",
            severity: "ERROR",
            retryable: statusCode >= 500,
            userMessage: "HTTP error occurred"
        }
    }
    
    ---
    {
        errorCode: "HTTP_" ++ statusCode,
        errorMessage: errorMessage,
        category: mappedError.category,
        severity: mappedError.severity,
        httpStatus: statusCode,
        retryable: mappedError.retryable,
        userMessage: mappedError.userMessage,
        details: httpError,
        timestamp: now() as String {format: "yyyy-MM-dd'T'HH:mm:ss'Z'"},
        source: "HTTP_CONNECTOR"
    }
}

/**
 * Maps MuleSoft runtime errors to standardized format
 * @param muleError - MuleSoft runtime error
 * @return Standardized error object
 */
fun mapMuleRuntimeError(muleError: Object): Object = do {
    var errorType = muleError.errorType default muleError.type default "MULE:UNKNOWN"
    var errorMessage = muleError.description default muleError.message default "MuleSoft runtime error"
    
    var mappedError = errorType match {
        case "MULE:TRANSFORMATION" -> {
            category: "TRANSFORMATION_ERROR",
            severity: "ERROR",
            httpStatus: 500,
            retryable: false,
            userMessage: "Data transformation error occurred"
        }
        case "MULE:EXPRESSION" -> {
            category: "EXPRESSION_ERROR",
            severity: "ERROR",
            httpStatus: 500,
            retryable: false,
            userMessage: "Expression evaluation error"
        }
        case "MULE:ROUTING" -> {
            category: "ROUTING_ERROR",
            severity: "ERROR",
            httpStatus: 500,
            retryable: false,
            userMessage: "Message routing error occurred"
        }
        case "MULE:CONNECTIVITY" -> {
            category: "CONNECTIVITY_ERROR",
            severity: "ERROR",
            httpStatus: 502,
            retryable: true,
            userMessage: "Connectivity error - unable to connect to service"
        }
        case "MULE:TIMEOUT" -> {
            category: "TIMEOUT_ERROR",
            severity: "WARNING",
            httpStatus: 504,
            retryable: true,
            userMessage: "Operation timeout occurred"
        }
        case "MULE:SECURITY" -> {
            category: "SECURITY_ERROR",
            severity: "ERROR",
            httpStatus: 401,
            retryable: false,
            userMessage: "Security validation failed"
        }
        else -> {
            category: "RUNTIME_ERROR",
            severity: "ERROR",
            httpStatus: 500,
            retryable: false,
            userMessage: "Runtime error occurred"
        }
    }
    
    ---
    {
        errorCode: errorType,
        errorMessage: errorMessage,
        category: mappedError.category,
        severity: mappedError.severity,
        httpStatus: mappedError.httpStatus,
        retryable: mappedError.retryable,
        userMessage: mappedError.userMessage,
        details: muleError,
        timestamp: now() as String {format: "yyyy-MM-dd'T'HH:mm:ss'Z'"},
        source: "MULE_RUNTIME"
    }
}

/**
 * Creates a standardized error response format
 * @param error - Mapped error object
 * @param correlationId - Request correlation ID
 * @return Standardized error response
 */
fun createErrorResponse(error: Object, correlationId: String = uuid()): Object = {
    error: {
        code: error.errorCode,
        message: error.errorMessage,
        category: error.category,
        severity: error.severity,
        userMessage: error.userMessage,
        retryable: error.retryable,
        details: error.details,
        timestamp: error.timestamp,
        correlationId: correlationId,
        source: error.source
    },
    httpStatus: error.httpStatus,
    success: false
}

/**
 * Determines retry strategy based on error type
 * @param error - Standardized error object
 * @return Retry strategy configuration
 */
fun getRetryStrategy(error: Object): Object = 
    if (error.retryable == true)
        error.category match {
            case "RATE_LIMITED" -> {
                strategy: "EXPONENTIAL_BACKOFF",
                maxRetries: 3,
                initialDelay: 5000,
                maxDelay: 30000,
                backoffMultiplier: 2.0
            }
            case "TIMEOUT_ERROR" -> {
                strategy: "LINEAR_BACKOFF",
                maxRetries: 2,
                initialDelay: 2000,
                maxDelay: 10000,
                backoffMultiplier: 1.0
            }
            case "CONNECTIVITY_ERROR" -> {
                strategy: "EXPONENTIAL_BACKOFF",
                maxRetries: 5,
                initialDelay: 1000,
                maxDelay: 16000,
                backoffMultiplier: 2.0
            }
            case "SERVICE_UNAVAILABLE" -> {
                strategy: "EXPONENTIAL_BACKOFF",
                maxRetries: 3,
                initialDelay: 10000,
                maxDelay: 60000,
                backoffMultiplier: 2.0
            }
            else -> {
                strategy: "LINEAR_BACKOFF",
                maxRetries: 2,
                initialDelay: 1000,
                maxDelay: 5000,
                backoffMultiplier: 1.0
            }
        }
    else {
        strategy: "NO_RETRY",
        maxRetries: 0,
        initialDelay: 0,
        maxDelay: 0,
        backoffMultiplier: 0.0
    }

/**
 * Extracts error context from various error formats
 * @param rawError - Raw error object from any source
 * @return Extracted error context
 */
fun extractErrorContext(rawError: Object): Object = {
    hasOracleError: rawError.errorCode != null or rawError.faultcode != null,
    hasHTTPError: rawError.statusCode != null or rawError.status != null,
    hasMuleError: rawError.errorType != null or rawError.type != null,
    errorSource: rawError match {
        case contains($ as String, "oracle") -> "ORACLE"
        case contains($ as String, "fusion") -> "FUSION"
        case contains($ as String, "soap") -> "SOAP"
        case contains($ as String, "http") -> "HTTP"
        case contains($ as String, "mule") -> "MULE"
        else -> "UNKNOWN"
    },
    originalError: rawError
}

/**
 * Routes error to appropriate mapper based on error type
 * @param rawError - Raw error object
 * @param correlationId - Request correlation ID
 * @return Standardized error response
 */
fun mapError(rawError: Object, correlationId: String = uuid()): Object = do {
    var context = extractErrorContext(rawError)
    
    var mappedError = if (context.hasOracleError and context.errorSource == "SOAP")
        mapFusionSOAPError(rawError)
    else if (context.hasOracleError)
        mapFusionRESTError(rawError)
    else if (context.hasHTTPError)
        mapHTTPError(rawError)
    else if (context.hasMuleError)
        mapMuleRuntimeError(rawError)
    else {
        errorCode: "UNKNOWN_ERROR",
        errorMessage: "Unknown error occurred",
        category: "UNKNOWN_ERROR",
        severity: "ERROR",
        httpStatus: 500,
        retryable: false,
        userMessage: "An unexpected error occurred",
        details: rawError,
        timestamp: now() as String {format: "yyyy-MM-dd'T'HH:mm:ss'Z'"},
        source: "UNKNOWN"
    }
    
    ---
    createErrorResponse(mappedError, correlationId)
}

/**
 * Validates error mapping configuration
 * @param config - Error mapping configuration
 * @return Validation result
 */
fun validateErrorMappingConfig(config: Object): Object = do {
    var errors = []
    
    var missingCategories = if (isEmpty(config.errorCategories default []))
        ["errorCategories configuration is required"]
    else []
    
    var invalidSeverities = if (!isEmpty(config.defaultSeverity default "") and 
                               !contains(["ERROR", "WARNING", "INFO"], config.defaultSeverity))
        ["defaultSeverity must be one of: ERROR, WARNING, INFO"]
    else []
    
    var allErrors = errors ++ missingCategories ++ invalidSeverities
    ---
    {
        isValid: isEmpty(allErrors),
        errors: allErrors
    }
}

/**
 * Generates error correlation metrics
 * @param errors - Array of error objects
 * @return Error metrics summary
 */
fun generateErrorMetrics(errors: Array): Object = do {
    var totalErrors = sizeOf(errors)
    var errorsByCategory = errors groupBy $.category
    var errorsBySeverity = errors groupBy $.severity
    var retryableErrors = errors filter $.retryable
    
    ---
    {
        totalErrors: totalErrors,
        categoryCounts: errorsByCategory mapObject ((categoryErrors, category) -> {
            (category): sizeOf(categoryErrors)
        }),
        severityCounts: errorsBySeverity mapObject ((severityErrors, severity) -> {
            (severity): sizeOf(severityErrors)
        }),
        retryableCount: sizeOf(retryableErrors),
        retryablePercentage: if (totalErrors > 0) 
            (sizeOf(retryableErrors) * 100 / totalErrors) 
        else 0,
        timestamp: now() as String {format: "yyyy-MM-dd'T'HH:mm:ss'Z'"}
    }
}