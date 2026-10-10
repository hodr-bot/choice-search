// Throwaway parser check: mirrors the functions to land in index.html.
const BUNDLE_RE = /bundle|\blot\b|\blots\b|x\s?\d+\s?(pcs|pieces|pack)|\d+\s?(pcs|pieces)\b|pack\s?deal|set\s?of|wholesale\s?lot/i;

function isAd(url) {
  return url.includes('aem_p4p_detail');
}

function isBundleLink(url) {
  return !/\/item\/(\d+)\.html/.test(url);
}

function hasPaidShipping(line) {
  return /Shipping:\s*\$|\+\s*\$\d[\d.]*\s*shipping/i.test(line);
}

function parseProductLine(line) {
  const links = [...line.matchAll(/\]\((https:\/\/[^)]+)\)/g)].map((m) => m[1]);
  if (!links.length) return null;
  const productUrl = links[links.length - 1];
  if (isAd(productUrl)) return null;
  const idMatch = /\/item\/(\d+)\.html/.exec(productUrl);
  if (!idMatch) return null; // BundleDeals or unknown link shape: not buyable
  const titleMatch = /###\s*([^$]+?)\s*\$/.exec(line);
  if (!titleMatch) return null;
  const title = titleMatch[1].trim();
  if (!title || BUNDLE_RE.test(title)) return null;
  const afterTitle = line.slice(titleMatch.index + titleMatch[0].length - 1);
  const priceMatch = /\$([\d.]+)/.exec(afterTitle);
  if (!priceMatch) return null;
  const price = parseFloat(priceMatch[1]);
  if (!Number.isFinite(price)) return null;
  if (hasPaidShipping(line)) return null;
  const imgMatch = /https:\/\/ae-pic-[^\s)]+/.exec(line);
  const rest = afterTitle.slice(priceMatch.index + priceMatch[0].length);
  // Rating: first decimal NOT starting right after "$" (skips $1.09 / $5.00 style prices).
  const ratingMatch = /(?<!\$)(\d\.\d)/.exec(rest);
  const soldMatch = /([\d,+]+\s*sold|\d+\s*sold)/i.exec(rest);
  const item = {
    id: idMatch[1],
    title,
    price: Math.round(price * 100) / 100,
    currency: 'USD',
    link: 'https://www.aliexpress.com/item/' + idMatch[1] + '.html',
    choice: /choice/i.test(line),
    freeShipping: /free shipping/i.test(line),
  };
  if (imgMatch) item.image = imgMatch[0];
  if (ratingMatch) item.rating = parseFloat(ratingMatch[1]);
  if (soldMatch) {
    const n = parseInt(soldMatch[1].replace(/[^\d]/g, ''), 10);
    if (Number.isFinite(n)) item.sales = n;
  }
  return item;
}

function parseJinaMarkdown(text) {
  const seen = new Set();
  const out = [];
  for (const raw of String(text).split('\n')) {
    const line = raw.trim();
    if (!line.includes('###') || !line.includes('](')) continue;
    const item = parseProductLine(line);
    if (item && !seen.has(item.id)) {
      seen.add(item.id);
      out.push(item);
      if (out.length >= 30) break;
    }
  }
  return out;
}

const { FIXTURES } = require('./fixture.check.js');
let pass = 0;
for (const fx of FIXTURES) {
  const got = parseProductLine(fx.line);
  const verdict = fx.expect === 'keep' ? got !== null : got === null;
  if (verdict) pass++;
  console.log((verdict ? 'PASS' : 'FAIL') + ' ' + fx.name + ' -> ' + JSON.stringify(got));
}
// Detail checks on the kept item
const kept = parseProductLine(FIXTURES[0].line);
const details =
  kept && kept.id === '3256803285802793' && kept.price === 1.09 &&
  kept.rating === 4.4 && kept.sales === 10000 &&
  kept.link === 'https://www.aliexpress.com/item/3256803285802793.html';
console.log((details ? 'PASS' : 'FAIL') + ' keep-details id/price/rating/sales/link');
console.log(pass + '/3 fixture lines as expected' + (details ? ', details OK' : ', DETAILS MISMATCH'));
process.exit(pass === 3 && details ? 0 : 1);
