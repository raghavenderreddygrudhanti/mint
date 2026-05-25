%dw 2.0
output application/java
var id = attributes.uriParams.taskId
var title = payload.title default ""
var description = payload.description default ""
var completed = attributes.queryParams.completed default false
var dueDate = attributes.queryParams.dueDate default ""
var setClause = [
        ("title = '$title'") if (!isEmpty(title)),
        ("description = '$description'") if (!isEmpty(description)),
        ("dueDate = '$dueDate'") if (!isEmpty(dueDate)),
        ("completed = $completed") if (!isEmpty(completed))
    ] joinBy ", "
---
"UPDATE tasks SET $setClause WHERE id = '$id'"