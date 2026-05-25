%dw 2.0

/**
 * Oracle Fusion Cloud Authentication Module
 * 
 * This module provides comprehensive authentication utilities for Oracle Fusion Cloud
 * integration including SAML assertion generation, JWT token handling, and OAuth2 flows.
 * 
 * Author: Oracle Fusion + MuleSoft Integration Team
 * Version: 1.0.0
 * Last Modified: 2024-06-24
 */

// Import required libraries
import * from dw::core::Strings
import * from dw::core::Arrays
import * from dw::Crypto
import fromBase64 from dw::core::Binaries
import toBase64 from dw::core::Binaries

/**
 * Generates SAML assertion for Oracle Fusion authentication
 * @param config - Authentication configuration object
 * @return SAML assertion as base64 encoded string
 */
fun generateSAMLAssertion(config: Object): String = do {
    var issueInstant = now() as String {format: "yyyy-MM-dd'T'HH:mm:ss'Z'"}
    var notOnOrAfter = (now() + |PT1H|) as String {format: "yyyy-MM-dd'T'HH:mm:ss'Z'"}
    var assertionId = "_" ++ uuid()
    
    var samlAssertion = 
    '<?xml version="1.0" encoding="UTF-8"?>
    <saml2:Assertion 
        xmlns:saml2="urn:oasis:names:tc:SAML:2.0:assertion"
        xmlns:xs="http://www.w3.org/2001/XMLSchema"
        ID="$(assertionId)"
        IssueInstant="$(issueInstant)"
        Version="2.0">
        <saml2:Issuer Format="urn:oasis:names:tc:SAML:2.0:nameid-format:entity">$(config.issuer)</saml2:Issuer>
        <saml2:Subject>
            <saml2:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified">$(config.username)</saml2:NameID>
            <saml2:SubjectConfirmation Method="urn:oasis:names:tc:SAML:2.0:cm:bearer">
                <saml2:SubjectConfirmationData 
                    NotOnOrAfter="$(notOnOrAfter)"
                    Recipient="$(config.audienceUri)" />
            </saml2:SubjectConfirmation>
        </saml2:Subject>
        <saml2:Conditions 
            NotBefore="$(issueInstant)"
            NotOnOrAfter="$(notOnOrAfter)">
            <saml2:AudienceRestriction>
                <saml2:Audience>$(config.audienceUri)</saml2:Audience>
            </saml2:AudienceRestriction>
        </saml2:Conditions>
        <saml2:AuthnStatement AuthnInstant="$(issueInstant)">
            <saml2:AuthnContext>
                <saml2:AuthnContextClassRef>urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport</saml2:AuthnContextClassRef>
            </saml2:AuthnContext>
        </saml2:AuthnStatement>
        <saml2:AttributeStatement>
            <saml2:Attribute Name="username">
                <saml2:AttributeValue xs:type="xs:string">$(config.username)</saml2:AttributeValue>
            </saml2:Attribute>
            <saml2:Attribute Name="email">
                <saml2:AttributeValue xs:type="xs:string">$(config.email default config.username ++ "@" ++ config.domain)</saml2:AttributeValue>
            </saml2:Attribute>
        </saml2:AttributeStatement>
    </saml2:Assertion>'
    ---
    toBase64(samlAssertion as Binary)
}

/**
 * Exchanges SAML assertion for JWT token from Oracle Fusion
 * @param samlAssertion - Base64 encoded SAML assertion
 * @param config - Authentication configuration
 * @return JWT token exchange request payload
 */
fun buildJWTTokenRequest(samlAssertion: String, config: Object): Object = {
    grant_type: "urn:ietf:params:oauth:grant-type:saml2-bearer",
    assertion: samlAssertion,
    client_id: config.clientId,
    client_secret: config.clientSecret,
    scope: config.scope default "urn:opc:resource:scope:all"
}

/**
 * Builds OAuth2 token request using password grant
 * @param config - Authentication configuration with username/password
 * @return OAuth2 password grant request payload
 */
fun buildPasswordGrantRequest(config: Object): Object = {
    grant_type: "password",
    username: config.username,
    password: config.password,
    client_id: config.clientId,
    client_secret: config.clientSecret,
    scope: config.scope default "urn:opc:resource:scope:all"
}

/**
 * Builds OAuth2 client credentials grant request
 * @param config - Authentication configuration with client credentials
 * @return OAuth2 client credentials request payload
 */
fun buildClientCredentialsRequest(config: Object): Object = {
    grant_type: "client_credentials",
    client_id: config.clientId,
    client_secret: config.clientSecret,
    scope: config.scope default "urn:opc:resource:scope:all"
}

/**
 * Validates and parses JWT token response
 * @param tokenResponse - Token response from Oracle Fusion
 * @return Parsed token information with expiration details
 */
fun parseTokenResponse(tokenResponse: Object): Object = do {
    var expiresIn = tokenResponse.expires_in default 3600
    var expirationTime = now() + ("PT" ++ expiresIn ++ "S" as Period)
    ---
    {
        accessToken: tokenResponse.access_token,
        tokenType: tokenResponse.token_type default "Bearer",
        expiresIn: expiresIn,
        expirationTime: expirationTime,
        refreshToken: tokenResponse.refresh_token,
        scope: tokenResponse.scope,
        isValid: tokenResponse.access_token != null,
        expiresAt: expirationTime as String {format: "yyyy-MM-dd'T'HH:mm:ss'Z'"}
    }
}

/**
 * Checks if a token is expired or about to expire
 * @param tokenInfo - Token information object
 * @param bufferMinutes - Buffer time in minutes before considering token expired
 * @return true if token needs refresh
 */
fun isTokenExpired(tokenInfo: Object, bufferMinutes: Number = 5): Boolean = do {
    var bufferTime = "PT" ++ bufferMinutes ++ "M" as Period
    var expirationWithBuffer = tokenInfo.expirationTime - bufferTime
    ---
    now() >= expirationWithBuffer
}

/**
 * Builds refresh token request
 * @param refreshToken - Refresh token from previous authentication
 * @param config - Authentication configuration
 * @return Refresh token request payload
 */
fun buildRefreshTokenRequest(refreshToken: String, config: Object): Object = {
    grant_type: "refresh_token",
    refresh_token: refreshToken,
    client_id: config.clientId,
    client_secret: config.clientSecret
}

/**
 * Generates OAuth2 authorization header
 * @param tokenInfo - Token information object
 * @return Authorization header value
 */
fun buildAuthorizationHeader(tokenInfo: Object): String = 
    (tokenInfo.tokenType default "Bearer") ++ " " ++ tokenInfo.accessToken

/**
 * Validates authentication configuration
 * @param config - Authentication configuration object
 * @return Validation result with errors if any
 */
fun validateAuthConfig(config: Object): Object = do {
    var errors = []

    var clientIdError = if (isEmpty(config.clientId default "")) 
        ["clientId is required"] 
        else []
    
    var clientSecretError = if (isEmpty(config.clientSecret default "")) 
        ["clientSecret is required"] 
        else []
    
    var baseUrlError = if (isEmpty(config.baseUrl default "")) 
        ["baseUrl is required"] 
        else []

    var allErrors = errors ++ clientIdError ++ clientSecretError ++ baseUrlError
    ---
    {
        isValid: isEmpty(allErrors),
        errors: allErrors
    }
}

/**
 * Generates correlation ID for request tracking
 * @return Unique correlation ID
 */
fun generateCorrelationId(): String = 
    "FUSION-" ++ (now() as Number) ++ "-" ++ (random() * 10000) as Number as String {format: "0000"}

/**
 * Builds common headers for Oracle Fusion API requests
 * @param tokenInfo - Token information
 * @param correlationId - Optional correlation ID
 * @return Headers object for HTTP requests
 */
fun buildFusionHeaders(tokenInfo: Object, correlationId: String = generateCorrelationId()): Object = {
    "Authorization": buildAuthorizationHeader(tokenInfo),
    "Content-Type": "application/json",
    "Accept": "application/json",
    "X-Correlation-ID": correlationId,
    "REST-Framework-Version": "6"
}

/**
 * Azure AD specific SAML assertion generation
 * @param azureConfig - Azure AD configuration
 * @return Azure AD compatible SAML assertion
 */
fun generateAzureADAssertion(azureConfig: Object): String = do {
    var issueInstant = now() as String {format: "yyyy-MM-dd'T'HH:mm:ss'Z'"}
    var notOnOrAfter = (now() + |PT1H|) as String {format: "yyyy-MM-dd'T'HH:mm:ss'Z'"}
    var assertionId = "_" ++ uuid()
    
    var azureSamlAssertion = 
    '<?xml version="1.0" encoding="UTF-8"?>
    <saml2:Assertion 
        xmlns:saml2="urn:oasis:names:tc:SAML:2.0:assertion"
        ID="$(assertionId)"
        IssueInstant="$(issueInstant)"
        Version="2.0">
        <saml2:Issuer>https://sts.windows.net/$(azureConfig.tenantId)/</saml2:Issuer>
        <saml2:Subject>
            <saml2:NameID Format="urn:oasis:names:tc:SAML:2.0:nameid-format:persistent">$(azureConfig.userId)</saml2:NameID>
            <saml2:SubjectConfirmation Method="urn:oasis:names:tc:SAML:2.0:cm:bearer">
                <saml2:SubjectConfirmationData 
                    NotOnOrAfter="$(notOnOrAfter)"
                    Recipient="$(azureConfig.audienceUri)" />
            </saml2:SubjectConfirmation>
        </saml2:Subject>
        <saml2:Conditions 
            NotBefore="$(issueInstant)"
            NotOnOrAfter="$(notOnOrAfter)">
            <saml2:AudienceRestriction>
                <saml2:Audience>$(azureConfig.audienceUri)</saml2:Audience>
            </saml2:AudienceRestriction>
        </saml2:Conditions>
        <saml2:AuthnStatement AuthnInstant="$(issueInstant)">
            <saml2:AuthnContext>
                <saml2:AuthnContextClassRef>urn:oasis:names:tc:SAML:2.0:ac:classes:Password</saml2:AuthnContextClassRef>
            </saml2:AuthnContext>
        </saml2:AuthnStatement>
        <saml2:AttributeStatement>
            <saml2:Attribute Name="http://schemas.microsoft.com/identity/claims/tenantid">
                <saml2:AttributeValue>$(azureConfig.tenantId)</saml2:AttributeValue>
            </saml2:Attribute>
            <saml2:Attribute Name="http://schemas.microsoft.com/identity/claims/objectidentifier">
                <saml2:AttributeValue>$(azureConfig.userId)</saml2:AttributeValue>
            </saml2:Attribute>
        </saml2:AttributeStatement>
    </saml2:Assertion>'
    ---
    toBase64(azureSamlAssertion as Binary)
}

/**
 * Error handling utility for authentication failures
 * @param error - Error response from authentication service
 * @return Standardized error response
 */
fun handleAuthError(error: Object): Object = {
    errorCode: error.error default "AUTH_ERROR",
    errorDescription: error.error_description default "Authentication failed",
    timestamp: now() as String {format: "yyyy-MM-dd'T'HH:mm:ss'Z'"},
    retryable: contains(error.error default "", "timeout") or contains(error.error default "", "network"),
    httpStatus: error.status default 401
}