%dw 2.0
output application/json
import * from dw::core::Strings
import * from dw::core::Dates

// Input: Oracle Fusion HCM Worker Response
// Output: Standardized Employee Format

---
{
    // Basic Information
    employeeId: payload.PersonId as String,
    employeeNumber: payload.PersonNumber,
    
    // Name Information
    fullName: payload.DisplayName,
    firstName: payload.FirstName,
    lastName: payload.LastName,
    middleName: payload.MiddleNames default null,
    
    // Contact Information
    email: lower(payload.WorkEmail) default lower(payload.PersonalEmail),
    workPhone: payload.WorkPhoneNumber replace " " with "" default null,
    mobilePhone: payload.MobilePhoneNumber replace " " with "" default null,
    
    // Employment Information
    jobTitle: payload.AssignmentName,
    department: {
        id: payload.DepartmentId as String,
        name: payload.DepartmentName
    },
    
    // Manager Information
    manager: if (payload.ManagerId != null) {
        id: payload.ManagerId as String,
        name: payload.ManagerDisplayName
    } else null,
    
    // Location Information
    location: {
        id: payload.LocationId as String default null,
        name: payload.LocationName default null,
        city: payload.City default null,
        country: payload.Country default null
    },
    
    // Dates
    hireDate: payload.HireDate as Date {format: "yyyy-MM-dd"},
    startDate: payload.AssignmentStartDate as Date {format: "yyyy-MM-dd"},
    
    // Calculate tenure in years
    tenureYears: (daysBetween(payload.HireDate as Date, now()) / 365) as Number {format: "#.#"},
    
    // Status
    status: payload.AssignmentStatus match {
        case status if (status == "ACTIVE") -> "Active"
        case status if (status == "INACTIVE") -> "Inactive"
        case status if (status == "SUSPEND") -> "Suspended"
        else -> "Unknown"
    },
    
    // Compensation (if available)
    compensation: if (payload.Salary != null) {
        salary: {
            amount: payload.Salary as Number,
            currency: payload.CurrencyCode default "USD",
            frequency: payload.SalaryBasis default "ANNUAL"
        },
        // Calculate hourly rate if annual
        (hourlyRate: (payload.Salary as Number / 2080)) if (payload.SalaryBasis == "ANNUAL")
    } else null,
    
    // Additional Attributes
    attributes: {
        grade: payload.GradeCode default null,
        jobCode: payload.JobCode,
        businessUnit: payload.BusinessUnitName,
        legalEntity: payload.LegalEntityName,
        payGroup: payload.PayrollName default null,
        unionCode: payload.UnionCode default null,
        (fte: payload.FTE as Number) if (payload.FTE != null)
    },
    
    // Metadata
    metadata: {
        source: "Oracle Fusion HCM",
        extractedAt: now() as String {format: "yyyy-MM-dd'T'HH:mm:ss'Z'"},
        version: "1.0"
    }
}

/* Example Input:
{
  "PersonId": 300100550668845,
  "PersonNumber": "EMP12345",
  "DisplayName": "John Michael Doe",
  "FirstName": "John",
  "LastName": "Doe",
  "MiddleNames": "Michael",
  "WorkEmail": "John.Doe@company.com",
  "WorkPhoneNumber": "+1 555 123 4567",
  "MobilePhoneNumber": "+1 555 987 6543",
  "AssignmentName": "Senior Software Engineer",
  "DepartmentId": 100,
  "DepartmentName": "Engineering",
  "ManagerId": 300100550668123,
  "ManagerDisplayName": "Jane Smith",
  "LocationId": 200,
  "LocationName": "HQ - San Francisco",
  "City": "San Francisco",
  "Country": "USA",
  "HireDate": "2019-03-15",
  "AssignmentStartDate": "2021-01-01",
  "AssignmentStatus": "ACTIVE",
  "Salary": 120000,
  "CurrencyCode": "USD",
  "SalaryBasis": "ANNUAL",
  "GradeCode": "E4",
  "JobCode": "SE003",
  "BusinessUnitName": "Technology",
  "LegalEntityName": "Company Inc.",
  "PayrollName": "US Biweekly",
  "FTE": 1.0
}
*/

/* Example Output:
{
  "employeeId": "300100550668845",
  "employeeNumber": "EMP12345",
  "fullName": "John Michael Doe",
  "firstName": "John",
  "lastName": "Doe",
  "middleName": "Michael",
  "email": "john.doe@company.com",
  "workPhone": "+15551234567",
  "mobilePhone": "+15559876543",
  "jobTitle": "Senior Software Engineer",
  "department": {
    "id": "100",
    "name": "Engineering"
  },
  "manager": {
    "id": "300100550668123",
    "name": "Jane Smith"
  },
  "location": {
    "id": "200",
    "name": "HQ - San Francisco",
    "city": "San Francisco",
    "country": "USA"
  },
  "hireDate": "2019-03-15",
  "startDate": "2021-01-01",
  "tenureYears": 4.8,
  "status": "Active",
  "compensation": {
    "salary": {
      "amount": 120000,
      "currency": "USD",
      "frequency": "ANNUAL"
    },
    "hourlyRate": 57.69
  },
  "attributes": {
    "grade": "E4",
    "jobCode": "SE003",
    "businessUnit": "Technology",
    "legalEntity": "Company Inc.",
    "payGroup": "US Biweekly",
    "unionCode": null,
    "fte": 1.0
  },
  "metadata": {
    "source": "Oracle Fusion HCM",
    "extractedAt": "2024-01-15T10:30:45Z",
    "version": "1.0"
  }
}
*/