/*
 * Contact Form -> Google Sheets
 * =============================
 * Acts as a tiny free "backend" that saves form messages to a Google Sheet.
 *
 * SETUP (one time):
 *   1. Open Google Sheets and create a new spreadsheet.
 *   2. Extensions -> Apps Script -> paste this whole file -> Save.
 *   3. Deploy -> New deployment -> type: Web app
 *        - Execute as:       Me
 *        - Who has access:   Anyone
 *        - Click Deploy, then Authorize access (grant read/write to your sheets).
 *   4. Copy the Web app URL (ends in /exec).
 *   5. In src/components/Contact.jsx set:
 *        const CONTACT_ENDPOINT = "https://script.google.com/macros/s/AKfycb...../exec";
 *
 * Messages land in a tab named "Contact Messages".
 */

var SHEET_NAME = "Contact Messages";

function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents);
    var name = String(body.name || "").trim();
    var email = String(body.email || "").trim();
    var message = String(body.message || "").trim();

    if (!name || !email || !message) {
      return respond_({ ok: false, error: "All fields are required." }, 400);
    }

    var sheet = ensureSheet_();
    sheet.appendRow([new Date(), name, email, message]);

    return respond_({ ok: true, message: "Message saved to the sheet." }, 200);
  } catch (err) {
    return respond_({ ok: false, error: String(err) }, 500);
  }
}

function doGet() {
  return respond_({ ok: true, status: "Contact endpoint is running." }, 200);
}

// Creates the sheet/tab if it does not exist yet, with a header row.
function ensureSheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
    sheet.appendRow(["Timestamp", "Name", "Email", "Message"]);
    sheet.setFrozenRows(1);
    sheet.getRange("A1:D1").setBackground("#0a0f1f");
    sheet.getRange("A1:D1").setFontColor("#ffffff").setFontWeight("bold");
  }
  return sheet;
}

function respond_(payload, code) {
  return ContentService.createTextOutput(JSON.stringify(payload)).setMimeType(
    ContentService.MimeType.JSON,
  );
}