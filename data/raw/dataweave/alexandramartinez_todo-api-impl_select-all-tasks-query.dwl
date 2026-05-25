%dw 2.0
output application/java
var completed = attributes.queryParams.completed
var dueDate = attributes.queryParams.dueDate
var whereClause = if (isEmpty(completed) and isEmpty(dueDate)) "" else "WHERE " ++ (
    [
        ("completed = $completed") if (!isEmpty(completed)),
        ("dueDate = '$dueDate'") if (!isEmpty(dueDate))
    ] joinBy " AND "
)
---
"SELECT * FROM tasks $whereClause"