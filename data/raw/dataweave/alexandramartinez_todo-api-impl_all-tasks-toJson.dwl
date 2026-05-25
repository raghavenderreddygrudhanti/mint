%dw 2.0
output application/json
---
payload map {
    id: $.id as String,
    title: $.title,
    (description: $.description) if (!isEmpty($.description)),
    (dueDate: $.dueDate) if (!isEmpty($.dueDate)),
    completed: $.completed
}