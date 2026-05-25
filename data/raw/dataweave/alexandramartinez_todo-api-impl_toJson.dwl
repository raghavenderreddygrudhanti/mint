%dw 2.0
output application/json
---
{
    id: payload[0].id,
    title: payload[0].title,
    (description: payload[0].description) if (!isEmpty(payload[0].description)),
    (dueDate: payload[0].dueDate) if (!isEmpty(payload[0].dueDate)),
    completed: payload[0].completed
}