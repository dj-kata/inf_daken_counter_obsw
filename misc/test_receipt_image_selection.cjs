// Run without extra dependencies: node --test misc/test_receipt_image_selection.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function load() {
  const source = fs.readFileSync(path.join(__dirname, '../template/mobile_score_viewer.html'), 'utf8');
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1];
  const elements = new Map();
  let rows = [];
  const classes = new Set();
  const opened = [];
  const element = (dataset = {}) => ({
    dataset, hidden: false, textContent: '', listeners: {},
    addEventListener(name, callback) { this.listeners[name] = callback; },
    click() { this.listeners.click?.({ preventDefault() {}, stopPropagation() {} }); },
  });
  const content = element();
  Object.defineProperty(content, 'innerHTML', {
    set(html) {
      this.html = html;
      for (const id of ['selectReceiptImagesBtn', 'selectionAction', 'combineImagesBtn']) elements.delete(id);
      rows = [];
      for (const match of html.matchAll(/<(?:button|div|details)\b([^>]*)>/g)) {
        const attributes = match[1];
        const dataset = {};
        for (const attr of attributes.matchAll(/data-([\w-]+)="([^"]*)"/g)) {
          dataset[attr[1].replace(/-([a-z])/g, (_, char) => char.toUpperCase())] = attr[2];
        }
        const node = element(dataset);
        const id = attributes.match(/\bid="([^"]*)"/);
        if (id) elements.set(id[1], node);
        rows.push(node);
      }
    },
    get() { return this.html; },
  });
  const querySelectorAll = selector => {
    const attr = selector.match(/^\[data-([\w-]+)\]$/)?.[1];
    if (!attr) return [];
    const key = attr.replace(/-([a-z])/g, (_, char) => char.toUpperCase());
    return rows.filter(row => key in row.dataset);
  };
  content.querySelectorAll = querySelectorAll;
  for (const id of ['content', 'stats', 'viewTitle', 'backBtn', 'homeBtn', 'settingsBtn']) {
    elements.set(id, id === 'content' ? content : element());
  }
  const context = vm.createContext({
    console, URLSearchParams,
    document: {
      getElementById: id => elements.get(id), querySelectorAll,
      body: { classList: {
        remove: name => classes.delete(name),
        toggle(name, on) { if (on) classes.add(name); else classes.delete(name); },
      } },
    },
    localStorage: { getItem() { return null; } },
    window: { open: (...args) => opened.push(args) },
  });
  // Load all application functions without starting navigation or network requests.
  vm.runInContext(script.slice(0, script.indexOf('    $("backBtn").addEventListener')), context);
  vm.runInContext('globalThis.appState = state;', context);
  context.loadReceiptCombinedImagesEnabled = () => true;
  context.summarySectionLimit = () => 10;
  context.filterSummaryResultRows = rows => rows;
  context.filterRankAchievementRows = rows => rows;
  return { context, elements, querySelectorAll, classes, opened };
}

const items = Array.from({ length: 35 }, (_, i) => ({
  image_id: `image-${i}`, chart_id: `chart-${i}`, title: `Song ${i}`, difficulty: 'SPA',
  lv: 12, score: 2000, pre_score: 1900, bp: 5, pre_bp: 10,
  lamp: 5, pre_lamp: 4, rank_achievement: 'AAA',
}));
const data = {
  folder: { label: 'RECEIPT' }, song_count: items.length,
  items, top_bpi_items: items, rank_achievement_updates: items,
  score_updates: items, lamp_updates: items, bp_updates: items,
};
const sections = ['play-log', 'top-bpi', 'rank-achievements', 'score-updates', 'lamp-updates', 'bp-updates'];

for (const section of sections) {
  test(`${section}: select full-list images, preserve on refresh, combine and cancel`, () => {
    const { context: c, elements, querySelectorAll: query, classes, opened } = load();
    c.renderReceiptSectionFull(section, data);
    assert.equal(query('[data-chart]').length, 35);
    assert.equal(query('[data-image-id]').length, 0);
    elements.get('selectReceiptImagesBtn').click();
    assert.equal(classes.has('selection-mode'), true);
    assert.equal(query('[data-image-id]').length, 35);
    query('[data-image-id]')[34].click();
    query('[data-image-id]')[10].click();
    c.renderReceiptSectionFull(section, data);
    assert.equal(c.appState.selectedImageIds.size, 2);
    assert.equal(elements.get('selectionAction').hidden, false);
    assert.equal(elements.get('combineImagesBtn').textContent, 'CREATE POST IMAGE (2)');
    assert.match(elements.get('stats').innerHTML, /SELECTED/);
    elements.get('combineImagesBtn').click();
    assert.equal(opened[0][0], '/api/combined-result-image?ids=image-34,image-10');
    query('[data-image-id]')[34].click();
    assert.equal(c.appState.selectedImageIds.size, 1);
    elements.get('selectReceiptImagesBtn').click();
    assert.equal(c.appState.selectedImageIds.size, 0);
    assert.equal(classes.has('selection-mode'), false);
    assert.equal(query('[data-image-id]').length, 0);
    assert.equal(elements.get('selectionAction').hidden, true);
  });
}

test('selection carries from truncated Receipt to full sections and back', () => {
  const { context: c, elements, querySelectorAll: query } = load();
  c.appState.view = 'receipt';
  c.renderReceipt(data);
  assert.equal(query('[data-receipt-full]').length, 6);
  elements.get('selectReceiptImagesBtn').click();
  query('[data-image-id]')[0].click();
  for (const section of sections) {
    c.renderReceiptSectionFull(section, data);
    assert.equal(c.appState.receiptImageSelection, true);
    assert.equal(query('[data-image-id]').length, 35);
    assert.equal(c.appState.selectedImageIds.has('image-0'), true);
  }
  c.appState.view = 'receipt';
  c.renderReceipt(data);
  assert.equal(c.appState.selectedImageIds.has('image-0'), true);
  assert.equal(elements.get('combineImagesBtn').textContent, 'CREATE POST IMAGE (1)');
});

test('disabled setting hides full-section selection controls; images are required for selection', () => {
  const { context: c, elements, querySelectorAll: query } = load();
  c.loadReceiptCombinedImagesEnabled = () => false;
  c.renderReceiptSectionFull('play-log', data);
  assert.equal(elements.has('selectReceiptImagesBtn'), false);
  assert.equal(elements.has('combineImagesBtn'), false);
  c.loadReceiptCombinedImagesEnabled = () => true;
  c.renderReceiptSectionFull('play-log', { ...data, items: [items[0], { ...items[1], image_id: null }] });
  elements.get('selectReceiptImagesBtn').click();
  assert.equal(query('[data-image-id]').length, 1);
});
