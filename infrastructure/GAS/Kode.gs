/* --- MAIN ROUTER --- */
function doGet(e) {
  return HtmlService.createTemplateFromFile('View_Index')
      .evaluate()
      .setTitle('WMS Mobile App')
      .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
      .addMetaTag('viewport', 'width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no');
}

function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}