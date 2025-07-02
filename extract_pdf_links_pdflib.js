const fs = require('fs');
const path = require('path');
const { PDFDocument } = require('pdf-lib');

async function extractLinksWithPdfLib(pdfPath, outPath) {
  const data = fs.readFileSync(pdfPath);
  const pdfDoc = await PDFDocument.load(data);
  const links = [];

  for (let i = 0; i < pdfDoc.getPageCount(); i++) {
    const page = pdfDoc.getPage(i);
    const annots = page.node.Annots();
    if (!annots) continue;
    const annotsArray = annots.asArray ? annots.asArray() : [];

    for (const annotRef of annotsArray) {
      const annot = pdfDoc.context.lookup(annotRef);
      const subtype = annot.get('Subtype');
      if (subtype && subtype.name === 'Link') {
        const rect = annot.get('Rect');
        let url = null;
        const a = annot.get('A');
        if (a && a.get('URI')) {
          url = a.get('URI');
        }
        if (url) {
          links.push({
            url: url,
            page: i + 1,
            rect: rect ? rect.toString() : ''
          });
        }
      }
    }
  }

  fs.writeFileSync(outPath, JSON.stringify(links, null, 2), 'utf8');
  console.log('Extracted links saved to', outPath);
}

(async () => {
  const pdfFile = 'NT105ML28112019.pdf';
  const pdfPath = path.join(__dirname, 'downloads', pdfFile);
  const outDir = path.join(__dirname, 'extracted_circulars', path.basename(pdfFile, '.pdf'));
  const linksPath = path.join(outDir, 'links.json');

  if (!fs.existsSync(pdfPath)) {
    console.error('PDF file does not exist:', pdfPath);
    process.exit(1);
  }
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  await extractLinksWithPdfLib(pdfPath, linksPath);
})(); 