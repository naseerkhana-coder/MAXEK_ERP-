# Staff Attendance Entry App

This is a simple Python desktop app for entering staff attendance and exporting the result to Excel.

## How to Run

Double-click:

```text
start_attendance_app.bat
```

The app saves entries to:

```text
attendance.xlsx
```

## Calculation

```text
Work Hours = End Time - Start Time - Break Time
Normal Hours = up to 8 hours
OT Hours = Work Hours over 8 hours
```

Example:

```text
Start: 08:00
End: 18:00
Break: 1:00
Work Hours: 9
Normal Hours: 8
OT Hours: 1
```
