const fs = require('fs');
const path = require('path');
const https = require('https');

// Sample RBI circular PDF URL
const pdfUrl = 'https://www.rbi.org.in/commonman/Upload/English/Notification/PDFs/NT105ML28112019.pdf';
const downloadsDir = path.join(__dirname, 'downloads');
const fileName = path.basename(pdfUrl);
const filePath = path.join(downloadsDir, fileName);

// Ensure downloads directory exists
if (!fs.existsSync(downloadsDir)) {
  fs.mkdirSync(downloadsDir);
}

function downloadPDF(url, dest, cb) {
  const file = fs.createWriteStream(dest);
  https.get(url, (response) => {
    if (response.statusCode !== 200) {
      cb(new Error(`Failed to get '${url}' (${response.statusCode})`));
      return;
    }
    response.pipe(file);
    file.on('finish', () => {
      file.close(cb);
    });
  }).on('error', (err) => {
    fs.unlink(dest, () => cb(err));
  });
}

downloadPDF(pdfUrl, filePath, (err) => {
  if (err) {
    console.error('Download failed:', err.message);
  } else {
    console.log(`PDF downloaded and saved to ${filePath}`);
  }
}); 