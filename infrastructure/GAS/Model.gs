const DB = {
  SHEET_TRANS: "Embalage",
  SHEET_CUST: "Customers",
  SHEET_CONF: "Configs",
  DATA_START_ROW: 7 ,// Sesuai request (Header A6, Data A7),
  SHEET_QUEUE: "PrintQueue",
  QUEUE_START_ROW: 2 // Header A1, Data A2
};

function _getSheet(name) {
  return SpreadsheetApp.getActiveSpreadsheet().getSheetByName(name);
}

// // --- CONFIGURATION REPO --- (deprecate)
// function getConfigs() {
//   const sheet = _getSheet(DB.SHEET_CONF);
//   const lastRow = sheet.getLastRow();
  
//   // Handle kalau config kosong biar gak error
//   const maxRow = lastRow < 4 ? 4 : lastRow; 

//   const items = sheet.getRange(`B4:B${maxRow}`).getValues().flat().filter(String);
//   const units = sheet.getRange(`C4:C${maxRow}`).getValues().flat().filter(String);
//   const tunnelUrl = sheet.getRange("F2").getValue(); // URL Ngrok
//   const zplFileId = sheet.getRange("F4").getValue(); // Sekarang isinya ID File
//   let zplTemplate = "";

//   try {
//     // Ambil isi file dari Drive berdasarkan ID
//     zplTemplate = DriveApp.getFileById(zplFileId).getBlob().getDataAsString();
//   } catch (e) {
//     zplTemplate = ""; // Handle error kalo ID salah/kosong
//   }

//   return { items, units, tunnelUrl, zplTemplate };
// }

/* --- Update di GAS/Model.gs --- */

function getConfigs() {
  const sheet = _getSheet(DB.SHEET_CONF);
  const lastRow = sheet.getLastRow();
  const maxRow = lastRow < 4 ? 4 : lastRow; 

  const items = sheet.getRange(`B4:B${maxRow}`).getValues().flat().filter(String);
  const units = sheet.getRange(`C4:C${maxRow}`).getValues().flat().filter(String);
  const tunnelUrl = sheet.getRange("F2").getValue();
  
  // --- UBAH BAGIAN INI ---
  const zplFileId = sheet.getRange("F4").getValue(); // Ambil ID File
  let zplTemplate = "";

  try {
    if (zplFileId) {
      // Baca isi file text dari Google Drive
      zplTemplate = DriveApp.getFileById(zplFileId).getBlob().getDataAsString();
    }
  } catch (e) {
    zplTemplate = ""; // Kalo error/ID salah, biarin kosong
    Logger.log("Error loading ZPL Template: " + e.message);
  }
  // -----------------------

  return { items, units, tunnelUrl, zplTemplate };
}

// --- EMBALAGE REPO ---
function addTransaction(data) {
  const sheet = _getSheet(DB.SHEET_TRANS);
  const timestamp = new Date();
  
  // Mapping Kolom: Timestamp, Tgl Form, Nama, Terima, Keluar, Ket
  const rowData = [
    timestamp,
    data.date,
    data.name,
    data.in || 0,
    data.out || 0,
    data.note || ""
  ];
  
  sheet.appendRow(rowData);
}

function getStockSummary() {
  const sheet = _getSheet(DB.SHEET_TRANS);
  const lastRow = sheet.getLastRow();
  
  if (lastRow < DB.DATA_START_ROW) return {}; // Belum ada data

  // Ambil data dari A7 sampai F terakhir
  const data = sheet.getRange(DB.DATA_START_ROW, 1, lastRow - DB.DATA_START_ROW + 1, 6).getValues();
  const stock = {};

  data.forEach(row => {
    const name = row[2]; // Nama Barang (Col C)
    const inQty = Number(row[3]) || 0; // Penerimaan (Col D)
    const outQty = Number(row[4]) || 0; // Pengeluaran (Col E)

    if (!stock[name]) stock[name] = 0;
    stock[name] += (inQty - outQty);
  });

  return stock;
}

// --- CUSTOMER REPO ---
function getCustomersList() {
  const sheet = _getSheet(DB.SHEET_CUST);
  const lastRow = sheet.getLastRow();
  
  if (lastRow < DB.DATA_START_ROW) return [];

  // Ambil data A7:L
  const data = sheet.getRange(DB.DATA_START_ROW, 1, lastRow - DB.DATA_START_ROW + 1, 12).getValues();

  return data.map(r => ({
    id: r[0],
    customerId: r[1],
    name: r[2],
    type: r[3],
    branch: r[4],    // Branch Name (Cabang)
    province: r[5],  // <--- TAMBAH INI (Kolom F)
    city: r[6],
    address: r[7],
    pic: r[9],
    phone: r[10]
  }));
}

// 1. Simpan Job Baru
function repoAddPrintJob(data) {
  const sheet = _getSheet(DB.SHEET_QUEUE);
  const id = Utilities.getUuid(); // Bikin ID Unik
  const now = new Date();
  
  // A:ID, B:Time, C:Name, D:Addr, E:Branch, F:Qty, G:Status, H:LastPrint
  const row = [
    id,
    now,
    data.customerName,
    data.address, // Kita simpan alamat mentah biar kalau master berubah, history tetep aman
    data.branch,
    data.qty,
    data.status || 'PENDING',
    '' // Last printed kosong dulu
  ];
  
  sheet.appendRow(row);
  return id; // Balikin ID buat dipake lanjut
}

// 2. Ambil List Antrian (Sort by Date Descending - Terbaru diatas)
function repoGetPrintJobs(limit = 50) {
  const sheet = _getSheet(DB.SHEET_QUEUE);
  const lastRow = sheet.getLastRow();
  if (lastRow < DB.QUEUE_START_ROW) return [];

  // Ambil semua data
  const data = sheet.getRange(DB.QUEUE_START_ROW, 1, lastRow - 1, 8).getValues();
  
  // Sort descending by Timestamp (Col B / Index 1) & Limit
  data.sort((a, b) => new Date(b[1]) - new Date(a[1]));
  const sliced = data.slice(0, limit);

  return sliced.map(r => ({
    id: r[0],
    date: Utilities.formatDate(new Date(r[1]), Session.getScriptTimeZone(), "dd/MM HH:mm"),
    name: r[2],
    address: r[3],
    branch: r[4],
    qty: r[5],
    status: r[6]
  }));
}

// 3. Update Status (Pas sukses print)
function repoUpdateJobStatus(jobId, status) {
  const sheet = _getSheet(DB.SHEET_QUEUE);
  const data = sheet.getDataRange().getValues();
  
  // Cari baris berdasarkan ID (Looping manual, simpel utk skala kecil)
  for (let i = 0; i < data.length; i++) {
    if (data[i][0] == jobId) {
      // Update Kolom G (Status) dan H (Last Printed)
      // Row index di sheet itu i+1
      sheet.getRange(i + 1, 7).setValue(status); 
      sheet.getRange(i + 1, 8).setValue(new Date());
      return true;
    }
  }
  return false;
}