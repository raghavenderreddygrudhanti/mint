"""
MINT — Comprehensive Negative & Correction Examples (v2)
==========================================================
50+ examples covering every common mistake the model can make.

Categories:
1. Mule 3 → Mule 4 corrections (15 examples)
2. Invalid/invented XML elements (10 examples)
3. Missing namespaces corrections (5 examples)
4. Off-topic rejection (5 examples)
5. Incomplete/ambiguous handling (5 examples)
6. Common connector mistakes (10 examples)
7. DataWeave mistakes (5 examples)

Usage:
    python scripts/generate_negative_examples_v2.py
"""

import json
from pathlib import Path

OUTPUT = Path("data/negative_examples.jsonl")

EXAMPLES = []

# ============================================================
# 1. MULE 3 → MULE 4 CORRECTIONS
# ============================================================
MULE3_CORRECTIONS = [
    ("Create a flow with inbound-endpoint for HTTP",
     "The `<inbound-endpoint>` is Mule 3 syntax and does NOT exist in Mule 4. Use `<http:listener>` instead:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:http=\"http://www.mulesoft.org/schema/mule/http\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/http http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd\">\n    <http:listener-config name=\"HTTP_Listener_config\">\n        <http:listener-connection host=\"0.0.0.0\" port=\"8081\" />\n    </http:listener-config>\n    <flow name=\"http-flow\">\n        <http:listener config-ref=\"HTTP_Listener_config\" path=\"/api\" />\n        <set-payload value='#[\"Hello from Mule 4\"]' />\n    </flow>\n</mule>"),
    ("Use outbound-endpoint to send data to another system",
     "The `<outbound-endpoint>` does NOT exist in Mule 4. Use connector-specific operations like `<http:request>`, `<kafka:publish>`, or `<jms:publish>`:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:http=\"http://www.mulesoft.org/schema/mule/http\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/http http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd\">\n    <http:request-config name=\"HTTP_Request_config\">\n        <http:request-connection host=\"${api.host}\" port=\"443\" protocol=\"HTTPS\" />\n    </http:request-config>\n    <flow name=\"send-data-flow\">\n        <http:request config-ref=\"HTTP_Request_config\" method=\"POST\" path=\"/api/data\">\n            <http:body><![CDATA[#[payload]]]></http:body>\n        </http:request>\n    </flow>\n</mule>"),
    ("Use catch-exception-strategy for error handling",
     "The `<catch-exception-strategy>` is Mule 3. In Mule 4, use `<error-handler>` with `<on-error-propagate>` or `<on-error-continue>`:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:ee=\"http://www.mulesoft.org/schema/mule/ee/core\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/ee/core http://www.mulesoft.org/schema/mule/ee/core/current/mule-ee.xsd\">\n    <flow name=\"error-handling-flow\">\n        <logger level=\"INFO\" message=\"Processing...\" />\n        <error-handler>\n            <on-error-propagate type=\"ANY\">\n                <ee:transform>\n                    <ee:message>\n                        <ee:set-payload><![CDATA[%dw 2.0\noutput application/json\n---\n{error: error.description, errorType: error.errorType.identifier}]]></ee:set-payload>\n                    </ee:message>\n                </ee:transform>\n            </on-error-propagate>\n        </error-handler>\n    </flow>\n</mule>"),
    ("Use MEL expression #[message.payload]",
     "MEL (Mule Expression Language) does NOT exist in Mule 4. Use DataWeave 2.0. Replace `#[message.payload]` with `#[payload]`:\n\n%dw 2.0\noutput application/json\n---\n{\n    data: payload,\n    timestamp: now(),\n    id: uuid()\n}"),
    ("Use session-variable to store data across flows",
     "Session variables do NOT exist in Mule 4. Use `<set-variable>` for flow variables, or Object Store for persistence across flows:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:os=\"http://www.mulesoft.org/schema/mule/os\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/os http://www.mulesoft.org/schema/mule/os/current/mule-os.xsd\">\n    <os:object-store name=\"myStore\" persistent=\"true\" />\n    <flow name=\"store-data-flow\">\n        <os:store key=\"#[vars.userId]\" objectStore=\"myStore\">\n            <os:value><![CDATA[#[payload]]]></os:value>\n        </os:store>\n    </flow>\n    <flow name=\"retrieve-data-flow\">\n        <os:retrieve key=\"#[vars.userId]\" objectStore=\"myStore\" target=\"storedData\" />\n    </flow>\n</mule>"),
]

for instr, output in MULE3_CORRECTIONS:
    EXAMPLES.append({"instruction": instr, "output": output, "metadata": {"type": "flow", "source": "negative_example", "category": "mule3_correction"}})

MULE3_CORRECTIONS_2 = [
    ("Use poll to schedule a task",
     "The `<poll>` element is Mule 3. In Mule 4, use `<scheduler>`:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd\">\n    <flow name=\"scheduled-flow\">\n        <scheduler>\n            <scheduling-strategy>\n                <fixed-frequency frequency=\"60\" timeUnit=\"SECONDS\" />\n            </scheduling-strategy>\n        </scheduler>\n        <logger level=\"INFO\" message=\"Scheduled task executed at #[now()]\" />\n    </flow>\n</mule>"),
    ("Use component ref to call a Java class",
     "The `<component ref>` is Mule 3. In Mule 4, use the Java Module `<java:invoke>`:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:java=\"http://www.mulesoft.org/schema/mule/java\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/java http://www.mulesoft.org/schema/mule/java/current/mule-java.xsd\">\n    <flow name=\"java-invoke-flow\">\n        <java:invoke class=\"com.example.MyService\" method=\"process(String)\">\n            <java:args><![CDATA[#[{arg0: payload}]]]></java:args>\n        </java:invoke>\n    </flow>\n</mule>"),
    ("Use expression-transformer to modify payload",
     "The `<expression-transformer>` does NOT exist in Mule 4. Use `<ee:transform>` with DataWeave:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:ee=\"http://www.mulesoft.org/schema/mule/ee/core\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/ee/core http://www.mulesoft.org/schema/mule/ee/core/current/mule-ee.xsd\">\n    <flow name=\"transform-flow\">\n        <ee:transform>\n            <ee:message>\n                <ee:set-payload><![CDATA[%dw 2.0\noutput application/json\n---\n{result: upper(payload.name)}]]></ee:set-payload>\n            </ee:message>\n        </ee:transform>\n    </flow>\n</mule>"),
    ("Use custom-transformer class",
     "The `<custom-transformer>` does NOT exist in Mule 4. Use DataWeave or Java Module:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:java=\"http://www.mulesoft.org/schema/mule/java\" xmlns:ee=\"http://www.mulesoft.org/schema/mule/ee/core\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/ee/core http://www.mulesoft.org/schema/mule/ee/core/current/mule-ee.xsd http://www.mulesoft.org/schema/mule/java http://www.mulesoft.org/schema/mule/java/current/mule-java.xsd\">\n    <flow name=\"custom-logic-flow\">\n        <ee:transform>\n            <ee:message>\n                <ee:set-payload><![CDATA[%dw 2.0\noutput application/json\n---\npayload map {\n    id: $.id,\n    name: capitalize($.name)\n}]]></ee:set-payload>\n            </ee:message>\n        </ee:transform>\n    </flow>\n</mule>"),
    ("Use message-properties-transformer to set HTTP headers",
     "The `<message-properties-transformer>` does NOT exist in Mule 4. Set headers directly on the connector:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:http=\"http://www.mulesoft.org/schema/mule/http\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/http http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd\">\n    <flow name=\"headers-flow\">\n        <http:request config-ref=\"HTTP_Request_config\" method=\"POST\" path=\"/api\">\n            <http:headers><![CDATA[#[{\n    'Content-Type': 'application/json',\n    'X-Correlation-Id': correlationId,\n    'Authorization': 'Bearer ' ++ vars.token\n}]]]></http:headers>\n        </http:request>\n    </flow>\n</mule>"),
    ("Use flow processingStrategy for async",
     "The `processingStrategy` attribute does NOT exist in Mule 4. Use `<async>` scope:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd\">\n    <flow name=\"async-flow\">\n        <http:listener config-ref=\"HTTP_Listener_config\" path=\"/trigger\" />\n        <async>\n            <flow-ref name=\"heavy-processing-subflow\" />\n        </async>\n        <set-payload value='{\"status\": \"accepted\"}' mimeType=\"application/json\" />\n    </flow>\n</mule>"),
]

for instr, output in MULE3_CORRECTIONS_2:
    EXAMPLES.append({"instruction": instr, "output": output, "metadata": {"type": "flow", "source": "negative_example", "category": "mule3_correction"}})

# ============================================================
# 2. INVALID/INVENTED XML — Never generate these
# ============================================================
INVALID_XML = [
    ("Create ICOMS integration flow",
     "ICOMS is a backend system — there is no `<icoms:>` connector in Mule 4. Connect to it via HTTP, Database, or Java Module:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:http=\"http://www.mulesoft.org/schema/mule/http\" xmlns:ee=\"http://www.mulesoft.org/schema/mule/ee/core\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/http http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd http://www.mulesoft.org/schema/mule/ee/core http://www.mulesoft.org/schema/mule/ee/core/current/mule-ee.xsd\">\n    <http:request-config name=\"ICOMS_Config\">\n        <http:request-connection host=\"${icoms.host}\" port=\"${icoms.port}\" />\n    </http:request-config>\n    <flow name=\"icoms-integration-flow\">\n        <http:listener config-ref=\"HTTP_Listener_config\" path=\"/api/icoms\" />\n        <ee:transform>\n            <ee:message>\n                <ee:set-payload><![CDATA[%dw 2.0\noutput application/json\n---\n{accountNumber: payload.accountNumber}]]></ee:set-payload>\n            </ee:message>\n        </ee:transform>\n        <http:request config-ref=\"ICOMS_Config\" method=\"POST\" path=\"/icoms/query\" />\n    </flow>\n</mule>"),
    ("Create a flow with method and return-type elements",
     "The `<method>` and `<return-type>` elements do NOT exist in Mule 4 XML. Never generate these. Use `<java:invoke>` for method calls:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:java=\"http://www.mulesoft.org/schema/mule/java\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/java http://www.mulesoft.org/schema/mule/java/current/mule-java.xsd\">\n    <flow name=\"invoke-flow\">\n        <java:invoke class=\"com.example.Service\" method=\"execute(String)\">\n            <java:args><![CDATA[#[{arg0: payload}]]]></java:args>\n        </java:invoke>\n    </flow>\n</mule>"),
    ("Create a flow with argument and parameter elements",
     "There are no `<argument>` or `<parameter>` elements in Mule 4 flow XML. To pass parameters, use variables or DataWeave:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:ee=\"http://www.mulesoft.org/schema/mule/ee/core\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/ee/core http://www.mulesoft.org/schema/mule/ee/core/current/mule-ee.xsd\">\n    <flow name=\"parameterized-flow\">\n        <set-variable variableName=\"param1\" value=\"#[attributes.queryParams.name]\" />\n        <set-variable variableName=\"param2\" value=\"#[attributes.queryParams.id]\" />\n        <flow-ref name=\"process-subflow\" />\n    </flow>\n</mule>"),
    ("Create a Netcracker connector flow",
     "There is no `<netcracker:>` connector in Mule 4. Netcracker is accessed via REST API using `<http:request>`:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:http=\"http://www.mulesoft.org/schema/mule/http\" xmlns:ee=\"http://www.mulesoft.org/schema/mule/ee/core\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/http http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd http://www.mulesoft.org/schema/mule/ee/core http://www.mulesoft.org/schema/mule/ee/core/current/mule-ee.xsd\">\n    <http:request-config name=\"Netcracker_Config\">\n        <http:request-connection host=\"${netcracker.host}\" port=\"443\" protocol=\"HTTPS\" />\n    </http:request-config>\n    <flow name=\"netcracker-query-flow\">\n        <http:request config-ref=\"Netcracker_Config\" method=\"GET\" path=\"/api/v1/products\">\n            <http:headers><![CDATA[#[{'Authorization': 'Bearer ' ++ vars.token}]]]></http:headers>\n            <http:query-params><![CDATA[#[{'offset': vars.offset, 'limit': vars.limit}]]]></http:query-params>\n        </http:request>\n    </flow>\n</mule>"),
    ("Create a Camunda connector flow",
     "There is no `<camunda:>` connector in Mule 4. Camunda is accessed via REST API:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:http=\"http://www.mulesoft.org/schema/mule/http\" xmlns:ee=\"http://www.mulesoft.org/schema/mule/ee/core\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/http http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd http://www.mulesoft.org/schema/mule/ee/core http://www.mulesoft.org/schema/mule/ee/core/current/mule-ee.xsd\">\n    <http:request-config name=\"Camunda_Config\">\n        <http:request-connection host=\"${camunda.host}\" port=\"8080\" />\n    </http:request-config>\n    <flow name=\"camunda-start-process-flow\">\n        <ee:transform>\n            <ee:message>\n                <ee:set-payload><![CDATA[%dw 2.0\noutput application/json\n---\n{variables: {orderId: {value: payload.orderId, type: \"String\"}}}]]></ee:set-payload>\n            </ee:message>\n        </ee:transform>\n        <http:request config-ref=\"Camunda_Config\" method=\"POST\" path=\"/engine-rest/process-definition/key/{processKey}/start\" />\n    </flow>\n</mule>"),
]

for instr, output in INVALID_XML:
    EXAMPLES.append({"instruction": instr, "output": output, "metadata": {"type": "flow", "source": "negative_example", "category": "invalid_xml_correction"}})

# ============================================================
# 3. NAMESPACE RULES — Always declare all prefixes
# ============================================================
NAMESPACE_EXAMPLES = [
    ("Create a flow with HTTP listener and DataWeave transform",
     "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:http=\"http://www.mulesoft.org/schema/mule/http\" xmlns:ee=\"http://www.mulesoft.org/schema/mule/ee/core\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:doc=\"http://www.mulesoft.org/schema/mule/documentation\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/http http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd http://www.mulesoft.org/schema/mule/ee/core http://www.mulesoft.org/schema/mule/ee/core/current/mule-ee.xsd\">\n    <http:listener-config name=\"HTTP_Listener_config\" doc:name=\"HTTP Listener config\">\n        <http:listener-connection host=\"0.0.0.0\" port=\"8081\" />\n    </http:listener-config>\n    <flow name=\"transform-flow\" doc:name=\"Transform Flow\">\n        <http:listener config-ref=\"HTTP_Listener_config\" path=\"/api/transform\" doc:name=\"Listener\" />\n        <ee:transform doc:name=\"Transform Message\">\n            <ee:message>\n                <ee:set-payload><![CDATA[%dw 2.0\noutput application/json\n---\n{\n    message: \"Hello\",\n    timestamp: now()\n}]]></ee:set-payload>\n            </ee:message>\n        </ee:transform>\n    </flow>\n</mule>"),
    ("Create a Salesforce query flow with error handling and logging",
     "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:salesforce=\"http://www.mulesoft.org/schema/mule/salesforce\" xmlns:ee=\"http://www.mulesoft.org/schema/mule/ee/core\" xmlns:http=\"http://www.mulesoft.org/schema/mule/http\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:doc=\"http://www.mulesoft.org/schema/mule/documentation\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/http http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd http://www.mulesoft.org/schema/mule/ee/core http://www.mulesoft.org/schema/mule/ee/core/current/mule-ee.xsd http://www.mulesoft.org/schema/mule/salesforce http://www.mulesoft.org/schema/mule/salesforce/current/mule-salesforce.xsd\">\n    <salesforce:sfdc-config name=\"Salesforce_Config\" doc:name=\"Salesforce Config\">\n        <salesforce:oauth-user-pass-connection consumerKey=\"${sf.consumerKey}\" consumerSecret=\"${sf.consumerSecret}\" username=\"${sf.username}\" password=\"${sf.password}\" securityToken=\"${sf.securityToken}\" />\n    </salesforce:sfdc-config>\n    <flow name=\"salesforce-query-flow\" doc:name=\"Salesforce Query\">\n        <http:listener config-ref=\"HTTP_Listener_config\" path=\"/api/accounts\" doc:name=\"Listener\" />\n        <salesforce:query config-ref=\"Salesforce_Config\" doc:name=\"Query Accounts\">\n            <salesforce:salesforce-query>SELECT Id, Name, Industry FROM Account WHERE Industry = ':industry'</salesforce:salesforce-query>\n            <salesforce:parameters><![CDATA[#[{industry: attributes.queryParams.industry}]]]></salesforce:parameters>\n        </salesforce:query>\n        <ee:transform doc:name=\"Map Response\">\n            <ee:message>\n                <ee:set-payload><![CDATA[%dw 2.0\noutput application/json\n---\npayload map {\n    id: $.Id,\n    name: $.Name,\n    industry: $.Industry\n}]]></ee:set-payload>\n            </ee:message>\n        </ee:transform>\n        <error-handler>\n            <on-error-propagate type=\"SALESFORCE:CONNECTIVITY\">\n                <ee:transform doc:name=\"Error Response\">\n                    <ee:message>\n                        <ee:set-payload><![CDATA[%dw 2.0\noutput application/json\n---\n{error: \"Salesforce connection failed\", detail: error.description}]]></ee:set-payload>\n                    </ee:message>\n                </ee:transform>\n            </on-error-propagate>\n        </error-handler>\n    </flow>\n</mule>"),
]

for instr, output in NAMESPACE_EXAMPLES:
    EXAMPLES.append({"instruction": instr, "output": output, "metadata": {"type": "flow", "source": "negative_example", "category": "namespace_complete"}})

# ============================================================
# 4. OFF-TOPIC REJECTION
# ============================================================
OFF_TOPIC = [
    ("What's the weather today?", "I'm MINT, specialized in MuleSoft 4 development. I can help with Mule 4 flows, DataWeave transformations, and connector configurations. What would you like to build?"),
    ("Write Python code to sort a list", "I specialize in MuleSoft 4 and DataWeave 2.0 only. I cannot help with Python. Would you like me to help with a MuleSoft integration instead?"),
    ("Explain quantum computing", "I'm MINT, an AI assistant for MuleSoft 4 development only. I can help with flow generation, DataWeave, connectors (Salesforce, SAP, Kafka, DB, etc.), and integration patterns. What MuleSoft project can I help you with?"),
    ("Create a React login page", "I only generate MuleSoft 4 code. I can't help with React, but I can build the backend API your React app would call using Mule 4 HTTP listener and APIkit."),
    ("Write a Java Spring Boot REST API", "I specialize in MuleSoft 4, not Spring Boot. In MuleSoft, REST APIs are built with HTTP Listener + APIkit Router. Would you like me to generate that instead?"),
    ("Tell me a joke", "I'm MINT — I only know MuleSoft 4 jokes like: Why did the flow fail? Because it had an unbound prefix! 😄 But seriously, how can I help with your MuleSoft project?"),
    ("How to deploy to AWS Lambda", "I specialize in MuleSoft 4 deployments (CloudHub, Runtime Fabric, on-premise). For calling AWS Lambda FROM Mule, I can help with that using the HTTP connector or AWS Lambda connector. Which do you need?"),
]

for instr, output in OFF_TOPIC:
    EXAMPLES.append({"instruction": instr, "output": output, "metadata": {"type": "flow", "source": "negative_example", "category": "off_topic"}})

# ============================================================
# 5. COMMON CONNECTOR MISTAKES
# ============================================================
CONNECTOR_FIXES = [
    ("Create a Salesforce flow using salesforce:select",
     "There is no `salesforce:select` operation. The correct operation is `salesforce:query`:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:salesforce=\"http://www.mulesoft.org/schema/mule/salesforce\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/salesforce http://www.mulesoft.org/schema/mule/salesforce/current/mule-salesforce.xsd\">\n    <flow name=\"sf-query-flow\">\n        <salesforce:query config-ref=\"Salesforce_Config\">\n            <salesforce:salesforce-query>SELECT Id, Name FROM Account</salesforce:salesforce-query>\n        </salesforce:query>\n    </flow>\n</mule>"),
    ("Use kafka:send to publish a message",
     "There is no `kafka:send` operation. The correct operation is `kafka:publish`:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:kafka=\"http://www.mulesoft.org/schema/mule/kafka\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/kafka http://www.mulesoft.org/schema/mule/kafka/current/mule-kafka.xsd\">\n    <flow name=\"kafka-publish-flow\">\n        <kafka:publish config-ref=\"Apache_Kafka_Producer_configuration\" topic=\"${kafka.topic}\">\n            <kafka:key><![CDATA[#[payload.id]]]></kafka:key>\n        </kafka:publish>\n    </flow>\n</mule>"),
    ("Use db:query to select from database",
     "The correct operation is `db:select` (not `db:query`):\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:db=\"http://www.mulesoft.org/schema/mule/db\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/db http://www.mulesoft.org/schema/mule/db/current/mule-db.xsd\">\n    <flow name=\"db-select-flow\">\n        <db:select config-ref=\"Database_Config\">\n            <db:sql>SELECT * FROM users WHERE id = :id</db:sql>\n            <db:input-parameters><![CDATA[#[{id: vars.userId}]]]></db:input-parameters>\n        </db:select>\n    </flow>\n</mule>"),
    ("Use http:listen to create an endpoint",
     "The correct element is `http:listener` (not `http:listen`):\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:http=\"http://www.mulesoft.org/schema/mule/http\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/http http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd\">\n    <http:listener-config name=\"HTTP_Listener_config\">\n        <http:listener-connection host=\"0.0.0.0\" port=\"8081\" />\n    </http:listener-config>\n    <flow name=\"api-flow\">\n        <http:listener config-ref=\"HTTP_Listener_config\" path=\"/api/v1/*\" />\n        <logger level=\"INFO\" message=\"#[payload]\" />\n    </flow>\n</mule>"),
    ("Use sftp:get to download a file",
     "The correct operation is `sftp:read` (not `sftp:get`):\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:sftp=\"http://www.mulesoft.org/schema/mule/sftp\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/sftp http://www.mulesoft.org/schema/mule/sftp/current/mule-sftp.xsd\">\n    <sftp:config name=\"SFTP_Config\">\n        <sftp:connection host=\"${sftp.host}\" username=\"${sftp.user}\" password=\"${sftp.password}\" />\n    </sftp:config>\n    <flow name=\"sftp-read-flow\">\n        <sftp:read config-ref=\"SFTP_Config\" path=\"/uploads/data.csv\" />\n    </flow>\n</mule>"),
]

for instr, output in CONNECTOR_FIXES:
    EXAMPLES.append({"instruction": instr, "output": output, "metadata": {"type": "flow", "source": "negative_example", "category": "connector_correction"}})

# ============================================================
# 6. DATAWEAVE MISTAKES
# ============================================================
DW_FIXES = [
    ("Write DataWeave using map on an object",
     "The `map` function works on Arrays, not Objects. For Objects, use `mapObject`:\n\n%dw 2.0\noutput application/json\n---\npayload mapObject (value, key) -> {\n    (upper(key)): value\n}"),
    ("Write DataWeave with output json",
     "The correct output type is `application/json` (not just `json`):\n\n%dw 2.0\noutput application/json\n---\n{\n    name: payload.firstName ++ \" \" ++ payload.lastName,\n    email: lower(payload.email)\n}"),
    ("Write DataWeave to loop through items",
     "DataWeave is functional — there are no loops. Use `map` for arrays:\n\n%dw 2.0\noutput application/json\n---\npayload.items map {\n    id: $.itemId,\n    name: $.itemName,\n    price: $.unitPrice * $.quantity\n}"),
    ("Write DataWeave with if/else statement",
     "DataWeave uses `if/else` as expressions (not statements). They must return a value:\n\n%dw 2.0\noutput application/json\n---\n{\n    status: if (payload.amount > 1000) \"high_value\"\n            else if (payload.amount > 100) \"medium_value\"\n            else \"low_value\",\n    approved: payload.amount <= vars.limit\n}"),
    ("Write DataWeave to parse a date string",
     "Use DataWeave's type coercion with format patterns:\n\n%dw 2.0\noutput application/json\n---\n{\n    originalDate: payload.dateStr,\n    parsed: payload.dateStr as Date {format: \"yyyy-MM-dd\"},\n    formatted: (payload.dateStr as Date {format: \"yyyy-MM-dd\"}) as String {format: \"dd/MM/yyyy\"},\n    now: now() as String {format: \"yyyy-MM-dd'T'HH:mm:ss\"}\n}"),
]

for instr, output in DW_FIXES:
    EXAMPLES.append({"instruction": instr, "output": output, "metadata": {"type": "dataweave", "source": "negative_example", "category": "dataweave_correction"}})

# ============================================================
# 7. AMBIGUOUS REQUESTS — Ask for clarification but still help
# ============================================================
AMBIGUOUS = [
    ("Create a flow",
     "Here's a basic Mule 4 HTTP API flow as a starting point. Tell me more about your use case (which connector, what data, error handling?) and I'll customize it:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:http=\"http://www.mulesoft.org/schema/mule/http\" xmlns:ee=\"http://www.mulesoft.org/schema/mule/ee/core\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/http http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd http://www.mulesoft.org/schema/mule/ee/core http://www.mulesoft.org/schema/mule/ee/core/current/mule-ee.xsd\">\n    <http:listener-config name=\"HTTP_Listener_config\">\n        <http:listener-connection host=\"0.0.0.0\" port=\"8081\" />\n    </http:listener-config>\n    <flow name=\"api-flow\">\n        <http:listener config-ref=\"HTTP_Listener_config\" path=\"/api/*\" />\n        <ee:transform>\n            <ee:message>\n                <ee:set-payload><![CDATA[%dw 2.0\noutput application/json\n---\n{status: \"success\", message: \"Hello from MINT\"}]]></ee:set-payload>\n            </ee:message>\n        </ee:transform>\n    </flow>\n</mule>"),
    ("Help with MuleSoft",
     "I can help with:\n- **Flows**: HTTP APIs, Kafka consumers, Salesforce integrations, batch jobs\n- **DataWeave**: JSON/XML/CSV transformations, mappings\n- **Connectors**: SAP, Salesforce, Database, Kafka, SFTP, JMS, AWS, Azure\n- **Patterns**: Error handling, scatter-gather, choice routing\n\nWhat are you building?"),
    ("Connect to SAP",
     "Here's a Mule 4 SAP connector flow. SAP supports IDoc, BAPI/RFC, and function calls:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:sap=\"http://www.mulesoft.org/schema/mule/sap\" xmlns:http=\"http://www.mulesoft.org/schema/mule/http\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/sap http://www.mulesoft.org/schema/mule/sap/current/mule-sap.xsd http://www.mulesoft.org/schema/mule/http http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd\">\n    <sap:config name=\"SAP_Config\">\n        <sap:simple-connection-provider-connection applicationServerHost=\"${sap.host}\" username=\"${sap.user}\" password=\"${sap.password}\" systemNumber=\"${sap.systemNumber}\" client=\"${sap.client}\" language=\"EN\" />\n    </sap:config>\n    <flow name=\"sap-bapi-flow\">\n        <http:listener config-ref=\"HTTP_Listener_config\" path=\"/api/sap/customers\" />\n        <sap:execute-synchronous-remote-function-call config-ref=\"SAP_Config\" key=\"BAPI_CUSTOMER_GETLIST\">\n            <sap:content><![CDATA[#[payload]]]></sap:content>\n        </sap:execute-synchronous-remote-function-call>\n    </flow>\n</mule>"),
]

for instr, output in AMBIGUOUS:
    EXAMPLES.append({"instruction": instr, "output": output, "metadata": {"type": "flow", "source": "negative_example", "category": "ambiguous_handled"}})

# ============================================================
# MAIN
# ============================================================
def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT, "w") as f:
        for example in EXAMPLES:
            f.write(json.dumps(example) + "\n")

    print(f"Generated {len(EXAMPLES)} negative/correction examples")
    print(f"Output: {OUTPUT}")
    print(f"\nBreakdown:")
    from collections import Counter
    cats = Counter(e["metadata"]["category"] for e in EXAMPLES)
    for cat, count in cats.most_common():
        print(f"  {cat}: {count}")
    print(f"\nTo add to training data:")
    print(f"  cat {OUTPUT} >> data/training_merged.jsonl")


if __name__ == "__main__":
    main()
