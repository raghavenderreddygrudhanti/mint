output application/java
---
if (isEmpty(vars.taskId)) {
    taskId: attributes.uriParams.taskId default vars.beforeUpdate.id
} else vars.taskId