/* --- API ENDPOINTS (Called by google.script.run) --- */

function apiInitApp() {
  const config = getConfigs();
  const stock = getStockSummary();
  return {
    items: config.items,
    units: config.units,
    stock: stock,
    // Kita gak kirim URL & Template ke frontend demi keamanan/kebersihan
  };
}

function apiSaveTransaction(payloadJson) {
  try {
    const payload = JSON.parse(payloadJson);
    const items = payload.items;
    
    items.forEach(item => {
      addTransaction({
        date: payload.date,
        name: item.name,
        in: item.inVal,
        out: item.outVal,
        note: item.note
      });
    });
    
    return { status: 'success', message: 'Data berhasil disimpan' };
  } catch (e) {
    return { status: 'error', message: e.toString() };
  }
}

function apiGetCustomers() {
  return getCustomersList();
}

function apiPrintLabel(customerId, boxQty) {
  try {
    // 1. Ambil Data
    const config = getConfigs();
    if (!config.tunnelUrl) throw new Error("URL Tunnel belum disetting di Configs!F3");
    
    const customers = getCustomersList();
    const customer = customers.find(c => c.id == customerId);
    if (!customer) throw new Error("Customer tidak ditemukan");

    // 2. Generate ZPL (Inject Data ke Template)
    let zpl = config.zplTemplate;
    
    // --> Logic Replace ZPL lu disini <--
    zpl = zpl.replace("recipient.customer", customer.name || "")
             .replace("recipient.full_address[0]", customer.address || "")
             .replace("recipient.city", customer.city || "")
             .replace("recipient.phone", customer.phone || "")
             .replace("box_info.current_box", boxQty || "1");

    // 3. Kirim ke Python Bridge (Laptop)
    // Payload disesuaikan sama script Python lu
    const payload = {
      "raw_zpl": zpl,
      "printer_id": "DEFAULT" // Opsional, tergantung python lu
    };

    const options = {
      'method' : 'post',
      'contentType': 'application/json',
      'payload' : JSON.stringify(payload),
      'muteHttpExceptions': true
    };

    // // Tembak URL Tunnel (F3)
    // // Endpoint /print-raw-zpl asumsi sesuai script python lu sebelumnya
    // const response = UrlFetchApp.fetch(`${config.tunnelUrl}/print-raw-zpl`, options);

    // Cek baris yang ada UrlFetchApp.fetch
// YANG LAMA (SALAH):
// const response = UrlFetchApp.fetch(`${config.tunnelUrl}/print-raw-zpl`, options);

    // GANTI JADI (BENAR):
    const cleanUrl = config.tunnelUrl.replace(/\/$/, ""); 
    const response = UrlFetchApp.fetch(`${cleanUrl}/api/proxy/direct-print`, options);
    
    if (response.getResponseCode() == 200) {
      return { status: 'success', message: 'Print command sent!' };
    } else {
      return { status: 'error', message: 'Printer Error: ' + response.getContentText() };
    }

  } catch (e) {
    return { status: 'error', message: e.message };
  }
}

/* --- API BARU BUAT QUEUE --- */

// 1. Cuma Simpan ke Antrian (Tanpa Print)
function apiAddToQueue(payloadJson) {
  try {
    const data = JSON.parse(payloadJson);
    repoAddPrintJob({
      customerName: data.name,
      address: data.address,
      branch: data.branch,
      qty: data.qty,
      status: 'PENDING'
    });
    return { status: 'success', message: 'Masuk antrian print!' };
  } catch (e) {
    return { status: 'error', message: e.message };
  }
}

// 2. Ambil Data History
function apiGetQueueList() {
  return repoGetPrintJobs(20); // Ambil 20 terakhir
}

// 3. Eksekusi Print (Bisa dari "Direct Print" atau "Reprint")
// Kalau direct: save dulu baru print. Kalau reprint: cuma print & update status.
// function apiExecutePrint(payloadJson) {
//   try {
//     const data = JSON.parse(payloadJson);
//     const config = getConfigs();
//     let jobId = data.jobId;

//     // Skenario A: Direct Print (Belum ada ID, simpan dulu)
//     if (!jobId) {
//       jobId = repoAddPrintJob({
//         customerName: data.name,
//         address: data.address,
//         branch: data.branch,
//         qty: data.qty,
//         status: 'PROCESSING'
//       });
//     }

//     // --- LOGIC GENERATE ZPL (Sama kayak sebelumnya) ---
//     if (!config.tunnelUrl) throw new Error("Tunnel mati bro");
    
//     let zpl = config.zplTemplate;
//     zpl = zpl.replace("recipient.customer", data.name || "")
//              .replace("recipient.full_address[0]", data.address || "")
//              .replace("recipient.branch", data.branch || "")
//              .replace("box_info.current_box", data.qty || "1");
//              // ... replace lainnya ...

//     // --- KIRIM KE PYTHON ---
//     const options = {
//       'method' : 'post',
//       'contentType': 'application/json',
//       'payload' : JSON.stringify({ "raw_zpl": zpl, "printer_id": "DEFAULT" }),
//       'muteHttpExceptions': true
//     };

//     const response = UrlFetchApp.fetch(`${config.tunnelUrl}/print-raw-zpl`, options);
    
//     // --- UPDATE STATUS ---
//     if (response.getResponseCode() == 200) {
//       repoUpdateJobStatus(jobId, 'PRINTED');
//       return { status: 'success', message: 'Print Sukses!' };
//     } else {
//       repoUpdateJobStatus(jobId, 'ERROR');
//       return { status: 'error', message: 'Gagal konek printer' };
//     }

//   } catch (e) {
//     return { status: 'error', message: e.message };
//   }
// }

/* --- GAS/Controller.gs --- */
/* --- Update di GAS/Controller.gs --- */

/* --- Update di GAS/Controller.gs --- */
/* --- GAS/Controller.gs --- */

function apiExecutePrint(payloadJson) {
  try {
    const data = JSON.parse(payloadJson);
    const config = getConfigs();
    let jobId = data.jobId;

    if (!jobId) {
      jobId = repoAddPrintJob({
        customerName: data.name,
        address: data.address,
        branch: data.branch,
        qty: data.qty,
        status: 'PROCESSING'
      });
    }

    let zpl = config.zplTemplate;
    if (!zpl) throw new Error("Template ZPL kosong/gagal load dari Drive (Cek Configs!F4)");

    // --- REPLACER "GALAK" (GLOBAL REPLACE) ---
    // Pake /g biar ke-replace SEMUA, bukan cuma yang pertama

    // 1. Data Customer (Muncul 2x di template, jadi wajib replaceAll/Regex Global)
    zpl = zpl.replace(/recipient\.customer/g, data.name || "")
             .replace(/recipient\.branch/g, data.branch || "");

    // 2. Alamat & Kontak (Pake replace biasa gpp karena cuma muncul sekali, tapi dibikin regex biar konsisten)
    zpl = zpl.replace(/recipient\.full_address\[0\]/g, data.address || "")
             .replace(/recipient\.full_address\[1\]/g, "") // Kosongin baris 2
             .replace(/contact : recipient\.contact/g, ""); // Kosongin kontak dulu

    // 3. Info Box
    zpl = zpl.replace(/box_info\.current_box/g, "1")
             .replace(/box_info\.total_box/g, data.qty || "1")
             .replace(/box_info\.petugas/g, "Admin")
             .replace(/box_info\.temperature/g, "Normal");

    // 4. Bersihin List Barang (name[0] - name[3])
    // Ini wajib loop karena ada index-nya
    for (let i = 0; i < 4; i++) {
       // Pake RegExp biar bisa nangkep kurung siku [ ]
       const rgxName = new RegExp(`name\\[${i}\\]`, 'g');
       const rgxQty = new RegExp(`qty\\[${i}\\]`, 'g');
       
       zpl = zpl.replace(rgxName, "").replace(rgxQty, "");
    }
    
    // --------------------------------------------------

    const payload = {
      "raw_zpl": zpl,
      "source": "GAS_MOBILE",
      "printer_id": "DEFAULT"
    };

    const cleanUrl = config.tunnelUrl.replace(/\/$/, ""); 
    const endpoint = `${cleanUrl}/api/proxy/direct-print`; 

    const options = {
      'method' : 'post',
      'contentType': 'application/json',
      'payload' : JSON.stringify(payload),
      'muteHttpExceptions': true
    };

    const response = UrlFetchApp.fetch(endpoint, options);
    
    if (response.getResponseCode() == 200) {
      repoUpdateJobStatus(jobId, 'PRINTED');
      return { status: 'success', message: 'Print Sukses!' };
    } else {
      return { status: 'error', message: 'Gagal: ' + response.getContentText() };
    }

  } catch (e) {
    return { status: 'error', message: e.message };
  }
}