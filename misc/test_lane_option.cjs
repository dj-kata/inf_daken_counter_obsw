// Run without extra dependencies: node --test misc/test_lane_option.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.join(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const shared = read('template/lane_option.js');

function load(file, search = '') {
    const elements = new Map();
    const classes = new Set();
    const properties = {'--show-lane-numbers': '0', '--show-when-idle': '0'};
    const events = {};
    const element = selector => {
        if (!elements.has(selector)) elements.set(selector, {
            innerHTML: '', style: {}, classList: {add() {}, remove() {}}
        });
        return elements.get(selector);
    };
    const context = {
        URLSearchParams, URL, Date, console: {log() {}},
        setInterval() {},
        window: {location: {search, hostname: '', href: 'file:///overlay/whole_layout.html'}, addEventListener() {}},
        localStorage: {getItem() { return null; }, setItem() {}},
        document: {
            body: {},
            documentElement: {classList: {toggle(name, enabled) {
                if (enabled) classes.add(name); else classes.delete(name);
            }}},
            addEventListener(name, callback) { events[name] = callback; },
            getElementById(id) { return id === 'random-lane-state' ? null : element(id); },
            querySelector: element, querySelectorAll() { return []; },
            createElement() { return {}; }, head: {appendChild() {}}
        },
        getComputedStyle() { return {getPropertyValue(name) { return properties[name] || ''; }}; }
    };
    vm.createContext(context);
    vm.runInContext(shared, context);
    if (file) {
        for (const match of read(file).matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)) {
            vm.runInContext(match[1], context);
        }
    }
    events.DOMContentLoaded();
    return {context, classes, properties, elements};
}

const digits = html => Array.from(html.matchAll(/lane-option-key-(\w+)">(\d)<\/span>/g));

test('all seven digits have the same markup and only their color class differs', () => {
    const {context} = load();
    const keys = digits(context.renderLaneOptionToken('RANDOM', '3172654'));
    assert.equal(keys.map(key => key[2]).join(''), '3172654');
    assert.deepEqual(keys.map(key => key[1]), ['white', 'red', 'white', 'blue', 'blue', 'white', 'blue']);
    assert.equal(digits(context.renderLaneOptionToken('REGULAR')).map(key => key[2]).join(''), '1234567');
    assert.equal(digits(context.renderLaneOptionToken('MIRROR')).map(key => key[2]).join(''), '7654321');
});

test('unknown, absent, or invalid layouts keep the original text', () => {
    const {context} = load();
    for (const option of ['RANDOM', 'R-RANDOM']) {
        for (const layout of [undefined, null, '', '1111111', '123456', '1234568']) {
            assert.equal(context.renderLaneOption(option, layout), option);
        }
    }
    assert.equal(context.renderLaneOption('S-RANDOM', '1234567'), 'S-RANDOM');
    assert.equal(context.renderLaneOption('RANDOM / RANDOM', '1234567'), 'RANDOM / RANDOM');
    assert.equal(digits(context.renderLaneOption('OFF / MIRROR')).length, 14);
});

test('default text and numeric alternatives preserve assists and escape text', () => {
    const {context} = load();
    const html = context.renderLaneOption('RANDOM, A-SCR', '3172654');
    assert.match(html, /lane-option-original">RANDOM<\/span>/);
    assert.match(html, /, A-SCR$/);
    assert.equal(digits(html).length, 7);
    assert.equal(context.renderLaneOption('<unknown>'), '&lt;unknown&gt;');
});

test('CSS defaults to text and can switch both ways without replacing result markup', () => {
    const {context, properties, classes} = load();
    assert.equal(classes.has('lane-numbers-enabled'), false);
    properties['--show-lane-numbers'] = '1';
    context.syncLaneOptionDisplay();
    assert.equal(classes.has('lane-numbers-enabled'), true);
    properties['--show-lane-numbers'] = '0';
    context.syncLaneOptionDisplay();
    assert.equal(classes.has('lane-numbers-enabled'), false);
});

test('iframe URL settings override standalone CSS in either direction', () => {
    const enabled = load(null, '?show_lane_numbers=1');
    assert.equal(enabled.classes.has('lane-numbers-enabled'), true);
    const disabled = load(null, '?show_lane_numbers=0');
    disabled.properties['--show-lane-numbers'] = '1';
    disabled.context.syncLaneOptionDisplay();
    assert.equal(disabled.classes.has('lane-numbers-enabled'), false);
});

test('today keeps its original colored abbreviations and offers numeric alternatives', () => {
    const {context, elements} = load('template/today_result.html');
    const html = context.renderOptionText('MIRROR, A-SCR');
    assert.match(html, /option-mirror">MIR<\/span>/);
    assert.match(html, /option-assist">A-SCR<\/span>/);
    assert.equal(digits(html).length, 7);
    assert.equal(digits(context.renderOptionText('RANDOM')).length, 0);
    context.updateTodayUpdates({items: [{opt: 'RANDOM', lane_layout: '3172654'}]});
    assert.equal(digits(elements.get('results-tbody').innerHTML).length, 7);
});

test('both history versions include alternatives for rows and independent score/BP records', () => {
    for (const file of ['template/history_cursong.html', 'template/v2/history_cursong.html']) {
        const {context, elements} = load(file);
        context.updateHistory({difficulty: 'SPA', notes: 1000, best_score: 1500,
            best_score_opt: 'MIRROR', best_bp: 10, best_bp_opt: 'RANDOM',
            best_bp_lane_layout: '7651234', items: [{opt: 'RANDOM', lane_layout: '3172654'}]});
        assert.equal(digits(elements.get('#result tbody').innerHTML).length, 7);
        const best = file.includes('/v2/') ? elements.get('#best tbody').innerHTML :
            elements.get('.score-info').innerHTML + elements.get('.bp-info').innerHTML;
        assert.equal(digits(best).length, 14);
        assert.match(best, /lane-option-original">MIRROR<\/span>/);
    }
});

test('whole_layout forwards the setting to both result frames and preserves other parameters', () => {
    const {context, properties} = load();
    const source = read('template/whole_layout.html');
    const func = source.match(/        function withWebSocketParams\(src\) \{[\s\S]*?\n        \}/)[0];
    context.getWebSocketHost = () => '127.0.0.1';
    context.getWebSocketPort = () => 8767;
    vm.runInContext(func, context);
    for (const value of ['0', '1']) {
        properties['--show-lane-numbers'] = value;
        for (const frame of ['history_cursong', 'today_result']) {
            const url = new URL(context.withWebSocketParams(`./${frame}.html?max_rows=8`));
            assert.equal(url.searchParams.get('show_lane_numbers'), value);
            assert.equal(url.searchParams.get('max_rows'), '8');
            assert.equal(url.searchParams.get('websocket_port'), '8767');
        }
    }
    assert.equal(new URL(context.withWebSocketParams('./clock.html')).searchParams.has('show_lane_numbers'), false);
});

test('random_lane stays numeric even with the default option-name setting', () => {
    const {context, elements} = load('template/random_lane.html');
    context.window.INFDC_RANDOM_LANE_STATE = {phase: 'confirmed', layout: '3172654'};
    context.render();
    assert.equal(digits(elements.get('layout').innerHTML).length, 7);
    assert.doesNotMatch(elements.get('layout').innerHTML, /lane-option-choice/);
});


test('partial layouts render color-only keys, known numbers, and unknown keys', () => {
    const {context} = load();
    const keys = html => Array.from(html.matchAll(/lane-option-key-(\w+)">([1-7]?)<\/span>/g));
    const colors = keys(context.renderLaneOptionToken('RANDOM', 'BWWBWWB'));
    assert.deepEqual(colors.map(key => key[1]), ['blue', 'white', 'white', 'blue', 'white', 'white', 'blue']);
    assert.ok(colors.every(key => key[2] === ''));
    const partial = keys(context.renderLaneOptionToken('R-RANDOM', 'B15BWWB'));
    assert.deepEqual(partial.map(key => key[2]), ['', '1', '5', '', '', '', '']);
    assert.equal(partial[1][1], 'red');
    const single = keys(context.renderLaneOptionToken('RANDOM', '???1???'));
    assert.equal(single.filter(key => key[1] === 'unknown').length, 6);
    for (const invalid of ['???????', 'WWWWWWW', 'BBBBBBB', '11?????', '<script']) {
        assert.equal(context.renderLaneOption('RANDOM', invalid), 'RANDOM');
    }
});

test('partial results appear in both histories and today results', () => {
    for (const file of ['template/history_cursong.html', 'template/v2/history_cursong.html']) {
        const {context, elements} = load(file);
        context.updateHistory({difficulty: 'SPA', notes: 1000, best_score: 1500,
            best_score_opt: 'RANDOM', best_score_lane_layout: '???1???',
            items: [{opt: 'RANDOM', lane_layout: 'BWWBWWB'}]});
        assert.match(elements.get('#result tbody').innerHTML, /lane-option-key-blue"><\/span>/);
    }
    const {context, elements} = load('template/today_result.html');
    context.updateTodayUpdates({items: [{opt: 'RANDOM', lane_layout: 'B15BWWB'}]});
    assert.equal(digits(elements.get('results-tbody').innerHTML).map(key => key[2]).join(''), '15');
});

test('live overlay shows partial layout, falls back to option, and retains partial when idle', () => {
    const {context, elements, properties} = load('template/random_lane.html');
    context.window.INFDC_RANDOM_LANE_STATE = {phase: 'analyzing', option: 'R-RANDOM'};
    context.render();
    assert.equal(elements.get('layout').innerHTML, 'R-RANDOM');
    context.window.INFDC_RANDOM_LANE_STATE = {phase: 'partial', option: 'R-RANDOM', layout: 'B15BWWB'};
    context.render();
    const partial = elements.get('layout').innerHTML;
    assert.equal(digits(partial).map(key => key[2]).join(''), '15');
    context.window.INFDC_RANDOM_LANE_STATE = {phase: 'waiting'};
    context.render();
    assert.equal(elements.get('layout').innerHTML, '');
    properties['--show-when-idle'] = '1';
    context.render();
    assert.equal(elements.get('layout').innerHTML, partial.replaceAll('R-RANDOM:', 'RANDOM:'));
    context.window.INFDC_RANDOM_LANE_STATE = {phase: 'failed', option: 'RANDOM', layout: ''};
    context.render();
    assert.equal(elements.get('layout').innerHTML, 'RANDOM');
});
