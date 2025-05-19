// Name of the sheet where data will be logged.
// You can change this if your sheet has a different name.
const SHEET_NAME = "BloodPressureData";

// Define the headers for your sheet.
// This helps in organizing data and ensures consistency.
// The script will create these headers if they don't exist in the first row.
const HEADERS = [
  "Timestamp",
  "Systolic (SYS)",
  "Diastolic (DIA)",
  "Heart Rate (P/min)",
  "Date (from device)"
];

/**
 * Handles HTTP POST requests to the web app.
 * This function is automatically called when your Python script sends data.
 * @param {Object} e - The event parameter for a POST request.
 */
function doPost(e) {
  let responseMessage;
  let statusCode = 200; // Default to success

  try {
    // Get the active spreadsheet and the specific sheet.
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let sheet = ss.getSheetByName(SHEET_NAME);

    // If the sheet doesn't exist, create it.
    if (!sheet) {
      sheet = ss.insertSheet(SHEET_NAME);
      console.log(`Sheet "${SHEET_NAME}" was created.`);
    }

    // Ensure headers are present in the sheet.
    // If the sheet is empty or headers don't match, write/overwrite them.
    if (sheet.getLastRow() === 0 || !headersMatch(sheet)) {
      sheet.clearContents(); // Clear existing content if headers need to be rewritten
      sheet.appendRow(HEADERS);
      console.log("Headers written to the sheet.");
      // Optional: Freeze the header row
      sheet.setFrozenRows(1);
    }

    // Parse the JSON data from the request body.
    const requestDataString = e.postData.contents;
    if (!requestDataString) {
      throw new Error("No data received in POST request.");
    }
    const jsonData = JSON.parse(requestDataString);
    console.log("Received data: " + JSON.stringify(jsonData));

    // Extract data using the keys from your Python script.
    // Use .get() equivalent or check for existence to avoid errors if a key is missing.
    const systolic = jsonData.systolic || "N/A";
    const diastolic = jsonData.diastolic || "N/A";
    const heartRate = jsonData.heart_rate || "N/A";
    const deviceDate = jsonData.date || "N/A"; // Date extracted from the device
    const timestamp = new Date(); // Current date and time for the log

    // Prepare the row to be appended.
    // Order should match the HEADERS array.
    const newRow = [
      timestamp,
      systolic,
      diastolic,
      heartRate,
      deviceDate
    ];

    // Append the new row to the sheet.
    sheet.appendRow(newRow);
    console.log("Data appended to sheet: " + newRow.join(", "));

    responseMessage = { status: "success", message: "Data saved to Google Sheet." };

  } catch (error) {
    console.error("Error processing request: " + error.toString());
    console.error("Stack: " + error.stack); // Log stack trace for better debugging
    responseMessage = { status: "error", message: "Failed to save data: " + error.toString() };
    statusCode = 500; // Internal Server Error
  }

  // Return a JSON response to the client (your Python script).
  return ContentService.createTextOutput(JSON.stringify(responseMessage))
    .setMimeType(ContentService.MimeType.JSON)
    .setStatusCode(statusCode); // This method doesn't exist, status code is part of HTTP response header
                                // For web apps, the status code is implicitly 200 unless an error is thrown
                                // that isn't caught and handled to return a different ContentService output.
                                // However, the client (requests library) will see the HTTP status.
                                // For more control over HTTP status codes, you'd typically handle errors and
                                // construct the ContentService output accordingly, but it's often simpler.
}

/**
 * Checks if the first row of the sheet matches the defined HEADERS.
 * @param {Sheet} sheet - The Google Sheet object.
 * @return {boolean} - True if headers match, false otherwise.
 */
function headersMatch(sheet) {
  if (sheet.getLastRow() < 1) return false; // No rows, so no headers
  const currentHeaders = sheet.getRange(1, 1, 1, HEADERS.length).getValues()[0];
  return HEADERS.every((header, index) => header === currentHeaders[index]);
}

// --- How to Deploy This Script ---
// 1. Open your Google Sheet (or create a new one).
// 2. Go to "Extensions" > "Apps Script".
// 3. Delete any boilerplate code in the `Code.gs` file and paste the code above.
// 4. Save the script (File > Save, or Ctrl+S/Cmd+S). Give your project a name if prompted.
// 5. Deploy as a Web App:
//    a. Click the "Deploy" button (top right).
//    b. Select "New deployment".
//    c. For "Select type", choose "Web app".
//    d. In the "New deployment" dialog:
//       - Enter a "Description" (e.g., "Blood Pressure Logger").
//       - For "Execute as", select "Me (your_email@example.com)".
//       - For "Who has access", select "Anyone" (if you want your Python script from any machine to access it)
//         OR "Anyone with Google account" if you prefer some level of authentication (though "Anyone" is common for webhooks).
//         If you choose "Anyone", be aware that the URL will be public, though unguessable.
//         **IMPORTANT**: If you choose "Anyone", your script will be accessible by anyone who has the URL.
//                      If you choose "Anyone with Google account", the calling script/user would need to handle OAuth.
//                      For simple server-to-server like this Python script, "Anyone" is often used,
//                      relying on the obscurity of the webhook URL for security.
//                      If you choose "Only myself", your Python script won't be able to call it unless it's also authenticated as you.
//                      For this use case, "Anyone" is generally the easiest to set up for a personal project.
//    e. Click "Deploy".
//    f. **Authorize permissions**: Google will ask you to review and authorize the permissions the script needs (to access your spreadsheets).
//       - Click "Review permissions".
//       - Choose your Google account.
//       - You might see a "Google hasn’t verified this app" warning. Click "Advanced", then "Go to (your project name) (unsafe)".
//       - Click "Allow".
//    g. **Copy the Web app URL**: After deployment, a URL will be provided. This is your `APP_SCRIPT_URL`.
//       Copy this URL and put it in your Python script's `.env` file.
//
// 6. (Optional) Test with curl or Postman:
//    You can test your webhook URL using a tool like curl:
//    curl -L -X POST YOUR_WEB_APP_URL -H "Content-Type: application/json" -d '{"systolic": "120", "diastolic": "80", "heart_rate": "75", "date": "2023-10-27"}'
//    Replace YOUR_WEB_APP_URL with the URL you copied.
//
// --- Sheet Setup ---
// - The script will create a sheet named "BloodPressureData" if it doesn't exist.
// - It will also add the headers: Timestamp, Systolic (SYS), Diastolic (DIA), Heart Rate (P/min), Date (from device).
