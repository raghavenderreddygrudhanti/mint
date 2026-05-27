"""
MINT — Generate Negative/Boundary Training Examples
=====================================================
Creates training pairs that teach the model:
1. Reject non-MuleSoft questions politely
2. Correct Mule 3 → Mule 4 migrations
3. Handle ambiguous/incomplete requests
4. Refuse harmful/irrelevant prompts

Add these to your training data before training v3.

Usage:
    python scripts/generate_negative_examples.py
    # Output: data/negative_examples.jsonl
"""

import json
from pathlib import Path

OUTPUT = Path("data/negative_examples.jsonl")

NEGATIVE_EXAMPLES = [
    # === CRITICAL: Never generate Mule 3 / invalid XML ===
    {
        "instruction": "Create a flow using component for ICOMS",
        "output": "In Mule 4, the `<component>` element from Mule 3 no longer exists. To invoke custom Java logic, use the Java Module (`<java:invoke>`):\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:java=\"http://www.mulesoft.org/schema/mule/java\" xmlns:http=\"http://www.mulesoft.org/schema/mule/http\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/java http://www.mulesoft.org/schema/mule/java/current/mule-java.xsd http://www.mulesoft.org/schema/mule/http http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd\">\n    <http:listener-config name=\"HTTP_Listener_config\">\n        <http:listener-connection host=\"0.0.0.0\" port=\"8081\" />\n    </http:listener-config>\n    <flow name=\"icoms-flow\">\n        <http:listener config-ref=\"HTTP_Listener_config\" path=\"/icoms\" />\n        <java:invoke class=\"com.example.IcomsProcessor\" method=\"execute(String)\">\n            <java:args><![CDATA[#[{arg0: payload}]]]></java:args>\n        </java:invoke>\n    </flow>\n</mule>",
        "metadata": {"type": "flow", "source": "negative_example", "category": "mule3_correction"}
    },
    {
        "instruction": "Create ICOMS integration flow",
        "output": "ICOMS (Integrated Communications Operations Management System) integration in Mule 4 typically uses HTTP or Database connectors to communicate with the ICOMS system. Here's a Mule 4 flow:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:http=\"http://www.mulesoft.org/schema/mule/http\" xmlns:ee=\"http://www.mulesoft.org/schema/mule/ee/core\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/http http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd http://www.mulesoft.org/schema/mule/ee/core http://www.mulesoft.org/schema/mule/ee/core/current/mule-ee.xsd\">\n    <http:request-config name=\"ICOMS_Request_config\">\n        <http:request-connection host=\"${icoms.host}\" port=\"${icoms.port}\" />\n    </http:request-config>\n    <flow name=\"icoms-integration-flow\">\n        <http:listener config-ref=\"HTTP_Listener_config\" path=\"/api/icoms\" />\n        <ee:transform>\n            <ee:message>\n                <ee:set-payload><![CDATA[%dw 2.0\noutput application/json\n---\n{\n    accountNumber: payload.accountNumber,\n    action: payload.action\n}]]></ee:set-payload>\n            </ee:message>\n        </ee:transform>\n        <http:request config-ref=\"ICOMS_Request_config\" method=\"POST\" path=\"/icoms/account\" />\n    </flow>\n</mule>",
        "metadata": {"type": "flow", "source": "negative_example", "category": "unknown_system"}
    },
    {
        "instruction": "Use component ref in a flow",
        "output": "The `<component ref>` syntax is from Mule 3 and does NOT exist in Mule 4. In Mule 4, to call Java classes use the Java Module:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:java=\"http://www.mulesoft.org/schema/mule/java\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/java http://www.mulesoft.org/schema/mule/java/current/mule-java.xsd\">\n    <java:config name=\"Java_Config\" />\n    <flow name=\"java-invoke-flow\">\n        <java:new class=\"com.example.MyProcessor\" constructor=\"MyProcessor()\" target=\"processor\" />\n        <java:invoke instance=\"#[vars.processor]\" class=\"com.example.MyProcessor\" method=\"process(String)\">\n            <java:args><![CDATA[#[{arg0: payload}]]]></java:args>\n        </java:invoke>\n    </flow>\n</mule>",
        "metadata": {"type": "flow", "source": "negative_example", "category": "mule3_correction"}
    },
    {
        "instruction": "Create a flow with method and return-type elements",
        "output": "The `<method>` and `<return-type>` elements do NOT exist in Mule 4 XML. These are invalid. In Mule 4, method invocation is done through the Java Module with DataWeave for type handling:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:java=\"http://www.mulesoft.org/schema/mule/java\" xmlns:ee=\"http://www.mulesoft.org/schema/mule/ee/core\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/java http://www.mulesoft.org/schema/mule/java/current/mule-java.xsd http://www.mulesoft.org/schema/mule/ee/core http://www.mulesoft.org/schema/mule/ee/core/current/mule-ee.xsd\">\n    <flow name=\"invoke-method-flow\">\n        <java:invoke class=\"com.example.Service\" method=\"processData(String, Integer)\">\n            <java:args><![CDATA[#[{arg0: payload.name, arg1: payload.count}]]]></java:args>\n        </java:invoke>\n        <ee:transform>\n            <ee:message>\n                <ee:set-payload><![CDATA[%dw 2.0\noutput application/json\n---\n{\n    result: payload,\n    type: typeOf(payload)\n}]]></ee:set-payload>\n            </ee:message>\n        </ee:transform>\n    </flow>\n</mule>",
        "metadata": {"type": "flow", "source": "negative_example", "category": "mule3_correction"}
    },
    # === Invalid Mule 4 elements the model should NEVER generate ===
    {
        "instruction": "Use expression-transformer in a flow",
        "output": "The `<expression-transformer>` does NOT exist in Mule 4. It was a Mule 3 component. In Mule 4, use `<ee:transform>` with DataWeave:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:ee=\"http://www.mulesoft.org/schema/mule/ee/core\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/ee/core http://www.mulesoft.org/schema/mule/ee/core/current/mule-ee.xsd\">\n    <flow name=\"transform-flow\">\n        <ee:transform>\n            <ee:message>\n                <ee:set-payload><![CDATA[%dw 2.0\noutput application/json\n---\n{\n    result: upper(payload.name),\n    timestamp: now()\n}]]></ee:set-payload>\n            </ee:message>\n        </ee:transform>\n    </flow>\n</mule>",
        "metadata": {"type": "flow", "source": "negative_example", "category": "mule3_correction"}
    },
    {
        "instruction": "Create a flow with custom-transformer",
        "output": "The `<custom-transformer>` element is from Mule 3 and does NOT exist in Mule 4. In Mule 4, custom transformations are done with DataWeave or the Java Module:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:java=\"http://www.mulesoft.org/schema/mule/java\" xmlns:ee=\"http://www.mulesoft.org/schema/mule/ee/core\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/ee/core http://www.mulesoft.org/schema/mule/ee/core/current/mule-ee.xsd http://www.mulesoft.org/schema/mule/java http://www.mulesoft.org/schema/mule/java/current/mule-java.xsd\">\n    <flow name=\"custom-transform-flow\">\n        <ee:transform>\n            <ee:message>\n                <ee:set-payload><![CDATA[%dw 2.0\noutput application/json\nimport * from dw::core::Strings\n---\npayload map {\n    id: $.id,\n    name: capitalize($.name),\n    email: lower($.email)\n}]]></ee:set-payload>\n            </ee:message>\n        </ee:transform>\n    </flow>\n</mule>",
        "metadata": {"type": "flow", "source": "negative_example", "category": "mule3_correction"}
    },
    {
        "instruction": "Use outbound-endpoint to send data",
        "output": "The `<outbound-endpoint>` is Mule 3 syntax and does NOT exist in Mule 4. In Mule 4, use the specific connector's operation (e.g., `<http:request>`, `<kafka:publish>`, `<jms:publish>`):\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:http=\"http://www.mulesoft.org/schema/mule/http\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/http http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd\">\n    <http:request-config name=\"HTTP_Request_config\">\n        <http:request-connection host=\"${api.host}\" port=\"443\" protocol=\"HTTPS\" />\n    </http:request-config>\n    <flow name=\"send-data-flow\">\n        <http:request config-ref=\"HTTP_Request_config\" method=\"POST\" path=\"/api/data\">\n            <http:body><![CDATA[#[payload]]]></http:body>\n            <http:headers><![CDATA[#[{'Content-Type': 'application/json'}]]]></http:headers>\n        </http:request>\n    </flow>\n</mule>",
        "metadata": {"type": "flow", "source": "negative_example", "category": "mule3_correction"}
    },
    {
        "instruction": "Use catch-exception-strategy for error handling",
        "output": "The `<catch-exception-strategy>` is Mule 3 syntax. In Mule 4, use `<error-handler>` with `<on-error-propagate>` or `<on-error-continue>`:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:http=\"http://www.mulesoft.org/schema/mule/http\" xmlns:ee=\"http://www.mulesoft.org/schema/mule/ee/core\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/http http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd http://www.mulesoft.org/schema/mule/ee/core http://www.mulesoft.org/schema/mule/ee/core/current/mule-ee.xsd\">\n    <flow name=\"error-handling-flow\">\n        <http:listener config-ref=\"HTTP_Listener_config\" path=\"/api/process\" />\n        <http:request config-ref=\"HTTP_Request_config\" method=\"GET\" path=\"/external\" />\n        <error-handler>\n            <on-error-propagate type=\"HTTP:CONNECTIVITY\">\n                <ee:transform>\n                    <ee:message>\n                        <ee:set-payload><![CDATA[%dw 2.0\noutput application/json\n---\n{\n    error: \"Service unavailable\",\n    message: error.description,\n    errorType: error.errorType.identifier\n}]]></ee:set-payload>\n                    </ee:message>\n                </ee:transform>\n                <set-variable variableName=\"httpStatus\" value=\"503\" />\n            </on-error-propagate>\n            <on-error-continue type=\"ANY\">\n                <ee:transform>\n                    <ee:message>\n                        <ee:set-payload><![CDATA[%dw 2.0\noutput application/json\n---\n{\n    error: \"Internal error\",\n    message: error.description\n}]]></ee:set-payload>\n                    </ee:message>\n                </ee:transform>\n                <set-variable variableName=\"httpStatus\" value=\"500\" />\n            </on-error-continue>\n        </error-handler>\n    </flow>\n</mule>",
        "metadata": {"type": "flow", "source": "negative_example", "category": "mule3_correction"}
    },
    {
        "instruction": "Use session-variable in Mule flow",
        "output": "Session variables do NOT exist in Mule 4. They were removed because Mule 4 uses a different execution model. Use regular variables with `<set-variable>` instead:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd\">\n    <flow name=\"variables-flow\">\n        <set-variable variableName=\"userId\" value=\"#[payload.userId]\" />\n        <set-variable variableName=\"correlationId\" value=\"#[uuid()]\" />\n        <set-variable variableName=\"timestamp\" value=\"#[now()]\" />\n        <logger level=\"INFO\" message=\"Processing user: #[vars.userId] with correlation: #[vars.correlationId]\" />\n    </flow>\n</mule>",
        "metadata": {"type": "flow", "source": "negative_example", "category": "mule3_correction"}
    },
    {
        "instruction": "Use poll scope to schedule a flow",
        "output": "The `<poll>` element is from Mule 3. In Mule 4, use `<scheduler>` as a flow source:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:http=\"http://www.mulesoft.org/schema/mule/http\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/http http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd\">\n    <flow name=\"scheduled-flow\">\n        <scheduler>\n            <scheduling-strategy>\n                <fixed-frequency frequency=\"30\" timeUnit=\"SECONDS\" />\n            </scheduling-strategy>\n        </scheduler>\n        <logger level=\"INFO\" message=\"Scheduled task running at #[now()]\" />\n        <http:request config-ref=\"HTTP_Request_config\" method=\"GET\" path=\"/api/sync\" />\n    </flow>\n</mule>",
        "metadata": {"type": "flow", "source": "negative_example", "category": "mule3_correction"}
    },
    # === Non-MuleSoft rejections ===
    {
        "instruction": "What's the weather today?",
        "output": "I'm MINT, specialized in MuleSoft 4 development. I can help you with:\n- Mule 4 flow generation (HTTP, Salesforce, Kafka, SAP, etc.)\n- DataWeave 2.0 transformations\n- Error handling patterns\n- Connector configurations\n\nWhat would you like to build?",
        "metadata": {"type": "flow", "source": "negative_example", "category": "off_topic"}
    },
    {
        "instruction": "Write a Python script to read a CSV file",
        "output": "I specialize in MuleSoft 4 and DataWeave only. For reading CSV in MuleSoft, here's a DataWeave approach:\n\n%dw 2.0\noutput application/json\n---\npayload map {\n    name: $.name,\n    email: $.email,\n    id: $.id\n}",
        "metadata": {"type": "dataweave", "source": "negative_example", "category": "redirect"}
    },
    {
        "instruction": "Create a React component for a login form",
        "output": "I'm MINT, focused exclusively on MuleSoft 4 development. I can't help with React, but I can help you build the backend API that your React login form would call:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:http=\"http://www.mulesoft.org/schema/mule/http\" xmlns:ee=\"http://www.mulesoft.org/schema/mule/ee/core\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/http http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd http://www.mulesoft.org/schema/mule/ee/core http://www.mulesoft.org/schema/mule/ee/core/current/mule-ee.xsd\">\n    <flow name=\"login-api-flow\">\n        <http:listener config-ref=\"HTTP_Listener_config\" path=\"/api/login\" allowedMethods=\"POST\" />\n        <ee:transform>\n            <ee:message>\n                <ee:set-payload><![CDATA[%dw 2.0\noutput application/json\n---\n{\n    token: uuid(),\n    user: payload.username,\n    expiresIn: 3600\n}]]></ee:set-payload>\n            </ee:message>\n        </ee:transform>\n    </flow>\n</mule>",
        "metadata": {"type": "flow", "source": "negative_example", "category": "redirect"}
    },
    {
        "instruction": "Explain quantum computing",
        "output": "I'm MINT, an AI assistant specialized in MuleSoft 4 development. I can help with Mule 4 flows, DataWeave transformations, connector configurations, and integration patterns. What MuleSoft project can I help you with?",
        "metadata": {"type": "flow", "source": "negative_example", "category": "off_topic"}
    },
    {
        "instruction": "Write SQL to create a users table",
        "output": "I specialize in MuleSoft 4, not raw SQL. But I can create a Mule 4 flow that executes SQL using the Database connector:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:db=\"http://www.mulesoft.org/schema/mule/db\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/db http://www.mulesoft.org/schema/mule/db/current/mule-db.xsd\">\n    <db:config name=\"Database_Config\">\n        <db:my-sql-connection host=\"${db.host}\" port=\"3306\" database=\"${db.name}\" user=\"${db.user}\" password=\"${db.password}\" />\n    </db:config>\n    <flow name=\"create-table-flow\">\n        <http:listener config-ref=\"HTTP_Listener_config\" path=\"/setup\" />\n        <db:execute-ddl config-ref=\"Database_Config\">\n            <db:sql>CREATE TABLE IF NOT EXISTS users (id INT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(255), email VARCHAR(255), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)</db:sql>\n        </db:execute-ddl>\n    </flow>\n</mule>",
        "metadata": {"type": "flow", "source": "negative_example", "category": "redirect"}
    },
    # === Ambiguous/incomplete requests ===
    {
        "instruction": "Create a flow",
        "output": "I'd be happy to help! Could you tell me more about what you need?\n\nFor example:\n- What system are you integrating with? (Salesforce, SAP, Kafka, Database, etc.)\n- What operation? (read, write, sync, transform)\n- Do you need error handling?\n- REST API or event-driven?\n\nHere's a basic HTTP listener flow as a starting point:\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<mule xmlns:http=\"http://www.mulesoft.org/schema/mule/http\" xmlns=\"http://www.mulesoft.org/schema/mule/core\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd http://www.mulesoft.org/schema/mule/http http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd\">\n    <http:listener-config name=\"HTTP_Listener_config\">\n        <http:listener-connection host=\"0.0.0.0\" port=\"8081\" />\n    </http:listener-config>\n    <flow name=\"my-flow\">\n        <http:listener config-ref=\"HTTP_Listener_config\" path=\"/api\" />\n        <logger level=\"INFO\" message=\"Request received: #[payload]\" />\n        <set-payload value='{\"status\": \"success\"}' mimeType=\"application/json\" />\n    </flow>\n</mule>",
        "metadata": {"type": "flow", "source": "negative_example", "category": "ambiguous"}
    },
    {
        "instruction": "Help me with MuleSoft",
        "output": "I can help with many MuleSoft 4 tasks:\n\n1. **Flow generation** — HTTP APIs, event-driven integrations, batch processing\n2. **DataWeave** — JSON/XML/CSV transformations, mappings, aggregations\n3. **Connectors** — Salesforce, SAP, Kafka, Database, SFTP, JMS, AWS, Azure\n4. **Patterns** — Error handling, scatter-gather, choice routing, async\n5. **Configs** — Global configs, secure properties, TLS\n\nTell me what you're building and I'll generate the code.",
        "metadata": {"type": "flow", "source": "negative_example", "category": "ambiguous"}
    },
]


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT, "w") as f:
        for example in NEGATIVE_EXAMPLES:
            f.write(json.dumps(example) + "\n")

    print(f"Generated {len(NEGATIVE_EXAMPLES)} negative/boundary examples")
    print(f"Output: {OUTPUT}")
    print(f"\nCategories:")
    from collections import Counter
    cats = Counter(e["metadata"]["category"] for e in NEGATIVE_EXAMPLES)
    for cat, count in cats.most_common():
        print(f"  {cat}: {count}")
    print(f"\nAdd these to your training data before training v3:")
    print(f"  cat {OUTPUT} >> data/training_merged.jsonl")


if __name__ == "__main__":
    main()
