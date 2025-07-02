const fs = require('fs');
const path = require('path');
const pdfParse = require('pdf-parse');

const pdfPath = path.join(__dirname, 'downloads', 'NT105ML28112019.pdf');

if (!fs.existsSync(pdfPath)) {
  console.error('PDF file does not exist:', pdfPath);
  process.exit(1);
}

const dataBuffer = fs.readFileSync(pdfPath);

pdfParse(dataBuffer)
  .then(data => {
    console.log('Extracted text from PDF:\n');
    console.log(data.text);
  })
  .catch(err => {
    console.error('Failed to extract text:', err);
  }); 