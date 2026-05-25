%dw 2.0
output application/json
import * from dw::core::Arrays
import * from dw::core::Objects

// Bulk update transformation for Oracle Fusion HCM
// Handles validation, error checking, and batch formatting

var maxBatchSize = 50
var validStatuses = ["ACTIVE", "INACTIVE", "TERMINATED", "SUSPENDED"]
var validUpdateFields = ["salary", "department", "manager", "jobTitle", "location"]

// Helper function to validate email format
fun isValidEmail(email: String): Boolean = 
    email matches /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/

// Helper function to validate date format
fun isValidDate(dateStr: String): Boolean = 
    dateStr matches /^\d{4}-\d{2}-\d{2}$/

// Helper function to check if update has valid fields
fun hasValidUpdateFields(update: Object): Boolean =
    keysOf(update) some ((key) -> validUpdateFields contains key as String)

// Helper function to create error record
fun createError(record: Object, errorType: String, message: String): Object = {
    originalRecord: record,
    error: {
        type: errorType,
        message: message,
        timestamp: now()
    }
}

// Main transformation
---
{
    // Split records into batches
    batches: (payload.updates divideBy maxBatchSize) map ((batch, batchIndex) -> {
        batchId: batchIndex + 1,
        records: batch map ((record, recordIndex) -> 
            // Validate each record
            if (isEmpty(record.employeeId))
                createError(record, "VALIDATION_ERROR", "Employee ID is required")
            else if (isEmpty(record.updates))
                createError(record, "VALIDATION_ERROR", "No updates provided")
            else if (not hasValidUpdateFields(record.updates))
                createError(record, "VALIDATION_ERROR", "No valid update fields provided")
            else if (record.updates.status? and not (validStatuses contains record.updates.status))
                createError(record, "VALIDATION_ERROR", "Invalid status value: $(record.updates.status)")
            else if (record.updates.email? and not isValidEmail(record.updates.email))
                createError(record, "VALIDATION_ERROR", "Invalid email format")
            else if (record.updates.hireDate? and not isValidDate(record.updates.hireDate))
                createError(record, "VALIDATION_ERROR", "Invalid date format. Use YYYY-MM-DD")
            else
                // Valid record - transform for Oracle Fusion API
                {
                    PersonId: record.employeeId,
                    
                    // Map update fields to Oracle Fusion fields
                    (Salary: record.updates.salary) if (record.updates.salary?),
                    (DepartmentId: record.updates.department.id) if (record.updates.department.id?),
                    (ManagerId: record.updates.manager.id) if (record.updates.manager.id?),
                    (AssignmentName: record.updates.jobTitle) if (record.updates.jobTitle?),
                    (LocationId: record.updates.location.id) if (record.updates.location.id?),
                    (AssignmentStatus: upper(record.updates.status)) if (record.updates.status?),
                    (WorkEmail: record.updates.email) if (record.updates.email?),
                    (WorkPhoneNumber: record.updates.workPhone) if (record.updates.workPhone?),
                    
                    // Add metadata
                    _metadata: {
                        updateRequestId: uuid(),
                        requestedAt: now(),
                        batchId: batchIndex + 1,
                        recordIndex: recordIndex + 1,
                        updateFields: keysOf(record.updates)
                    }
                }
        ),
        
        // Batch summary
        summary: {
            totalRecords: sizeOf(batch),
            validRecords: sizeOf(batch filter (not ($.error?))),
            errorRecords: sizeOf(batch filter ($.error?))
        }
    }),
    
    // Overall summary
    summary: {
        totalRecords: sizeOf(payload.updates),
        totalBatches: sizeOf(payload.updates divideBy maxBatchSize),
        validRecords: sizeOf(payload.updates filter ((record) -> 
            not isEmpty(record.employeeId) and 
            not isEmpty(record.updates) and
            hasValidUpdateFields(record.updates)
        )),
        errorRecords: sizeOf(payload.updates filter ((record) -> 
            isEmpty(record.employeeId) or 
            isEmpty(record.updates) or
            not hasValidUpdateFields(record.updates)
        )),
        processedAt: now(),
        maxBatchSize: maxBatchSize
    }
}

/* Example Input:
{
  "updates": [
    {
      "employeeId": "300100550668845",
      "updates": {
        "salary": 125000,
        "department": {
          "id": "200"
        }
      }
    },
    {
      "employeeId": "300100550668846",
      "updates": {
        "status": "ACTIVE",
        "manager": {
          "id": "300100550668123"
        },
        "jobTitle": "Lead Software Engineer"
      }
    },
    {
      "employeeId": "",
      "updates": {
        "salary": 90000
      }
    },
    {
      "employeeId": "300100550668847",
      "updates": {
        "email": "invalid-email",
        "status": "INVALID_STATUS"
      }
    }
  ]
}
*/

/* Example Output:
{
  "batches": [
    {
      "batchId": 1,
      "records": [
        {
          "PersonId": "300100550668845",
          "Salary": 125000,
          "DepartmentId": "200",
          "_metadata": {
            "updateRequestId": "550e8400-e29b-41d4-a716-446655440000",
            "requestedAt": "2024-01-15T10:30:45.123Z",
            "batchId": 1,
            "recordIndex": 1,
            "updateFields": ["salary", "department"]
          }
        },
        {
          "PersonId": "300100550668846",
          "AssignmentStatus": "ACTIVE",
          "ManagerId": "300100550668123",
          "AssignmentName": "Lead Software Engineer",
          "_metadata": {
            "updateRequestId": "550e8400-e29b-41d4-a716-446655440001",
            "requestedAt": "2024-01-15T10:30:45.123Z",
            "batchId": 1,
            "recordIndex": 2,
            "updateFields": ["status", "manager", "jobTitle"]
          }
        },
        {
          "originalRecord": {
            "employeeId": "",
            "updates": {
              "salary": 90000
            }
          },
          "error": {
            "type": "VALIDATION_ERROR",
            "message": "Employee ID is required",
            "timestamp": "2024-01-15T10:30:45.123Z"
          }
        },
        {
          "originalRecord": {
            "employeeId": "300100550668847",
            "updates": {
              "email": "invalid-email",
              "status": "INVALID_STATUS"
            }
          },
          "error": {
            "type": "VALIDATION_ERROR",
            "message": "Invalid email format",
            "timestamp": "2024-01-15T10:30:45.123Z"
          }
        }
      ],
      "summary": {
        "totalRecords": 4,
        "validRecords": 2,
        "errorRecords": 2
      }
    }
  ],
  "summary": {
    "totalRecords": 4,
    "totalBatches": 1,
    "validRecords": 2,
    "errorRecords": 2,
    "processedAt": "2024-01-15T10:30:45.123Z",
    "maxBatchSize": 50
  }
}
*/