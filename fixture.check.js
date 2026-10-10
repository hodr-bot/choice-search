// Fixture lines built from brief spec (no host access to /tmp/jina.txt in jail).
// Line A: KEEP (brief line 98 style) — expected: kept, id 3256803285802793, $1.09, rating 4.4, sold.
// Line B: bundle-link EXCLUDE (brief line 111 style, ssr/BundleDeals, no /item/ID).
// Line C: ad EXCLUDE (brief line 104 style, aem_p4p_detail + bundle title).
const FIXTURES = [
  {
    name: 'keep-esp32cam',
    line: '[![Image 98: ESP32-CAM WiFi Module Bluetooth Development Board Nodemcu](https://ae-pic-a1.aliexpress-media.com/kf/Sabcdef1234.avif) ![star](https://ae-pic-star.png) ### ESP32-CAM WiFi Module Bluetooth Development Board Nodemcu $1.09 $5.00 -78% 4.4 10,000+ sold Choice Free shipping](https://www.aliexpress.us/item/3256803285802793.html?spm=a2g0o.detail.1000014.1)',
    expect: 'keep',
  },
  {
    name: 'bundle-link-excluded',
    line: '[![Image 111: ESP32 Bundle Deals Pack](https://ae-pic-a1.aliexpress-media.com/kf/Sbundle999.avif) ### ESP32 Bundle Deals Pack $9.99 4.8 2,000+ sold](https://www.aliexpress.us/ssr/300000512/BundleDeals2?productIds=3256801111111,3256802222222)',
    expect: 'exclude',
  },
  {
    name: 'ad-excluded',
    line: '[![Image 104: 10PCS ESP32 Dev Boards Lot Pack](https://ae-pic-a1.aliexpress-media.com/kf/Sad7777.avif) ### 10PCS ESP32 Dev Boards Lot Pack $11.79 $15.00 -21% 4.9 500+ sold](https://www.aliexpress.us/item/3256809999999.html?pdp_npi=1&aem_p4p_detail=20240101xyz)',
    expect: 'exclude',
  },
];
module.exports = { FIXTURES };
