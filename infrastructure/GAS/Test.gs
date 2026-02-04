/* --- GAS/Test.gs (Buat file baru atau taruh di paling bawah Controller) --- */

function testKoneksiKeHost() {
  // 1. Ambil Config
  const config = getConfigs();
  const cleanUrl = config.tunnelUrl.replace(/\/$/, "");
  const endpoint = `${cleanUrl}/api/proxy/direct-print`;
  
  Logger.log("Target URL: " + endpoint);

  // 2. Dummy ZPL (Cuma print text sederhana buat hemat kertas label)
  // ^XA^FO50,50^ADN,36,20^FDTEST KONEKSI DARI GAS^FS^XZ
  const dummyZpl = "^XA^FO50,50^ADN,36,20^FDTEST CONNECTION OK^FS^XZ";

  // 3. Payload
  const payload = {
    "raw_zpl": dummyZpl,
    "source": "GAS_DEBUGGER",
    "printer_id": "DEFAULT"
  };

  const options = {
    'method' : 'post',
    'contentType': 'application/json',
    'payload' : JSON.stringify(payload),
    'muteHttpExceptions': true
  };

  try {
    Logger.log("Mengirim request...");
    const response = UrlFetchApp.fetch(endpoint, options);
    
    Logger.log("Response Code: " + response.getResponseCode());
    Logger.log("Response Body: " + response.getContentText());
    
    if (response.getResponseCode() == 200) {
      Logger.log("✅ SUKSES! Printer harusnya gerak sekarang.");
    } else {
      Logger.log("❌ GAGAL! Cek log error di atas.");
    }
  } catch (e) {
    Logger.log("❌ ERROR KONEKSI: " + e.message);
    Logger.log("Pastikan Tunnel nyala dan URL di Sheet Configs!F3 bener.");
  }
}