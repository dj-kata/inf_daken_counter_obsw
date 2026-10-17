function escapeLaneOptionText(value) {
    return String(value).replace(/[&<>"']/g, function(character) {
        return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character];
    });
}

// Return an empty string when the caller should keep its existing text rendering.
function renderLaneOptionToken(token, savedLayout) {
    var option = String(token || '').trim().toUpperCase();
    var layout;
    if (['REGULAR', 'OFF', 'NORMAL'].includes(option)) {
        layout = '1234567';
    } else if (['MIRROR', 'MIR'].includes(option)) {
        layout = '7654321';
    } else if (['RANDOM', 'RAN', 'R-RANDOM', 'R-RAN'].includes(option)) {
        layout = savedLayout;
    }
    if (typeof layout !== 'string' || !/^[1-7]{7}$/.test(layout) || new Set(layout).size !== 7) {
        return '';
    }
    var label = escapeLaneOptionText(option + ': ' + layout);
    return '<span class="lane-option" role="img" aria-label="' + label + '" title="' + label + '">' +
        Array.from(layout, function(lane) {
            var position = -61 * (Number(lane) - 1) / 100;
            return '<span class="lane-option-key" style="background-position:' + position + 'em 0"></span>';
        }).join('') + '</span>';
}

function renderLaneOption(opt, savedLayout) {
    // A single saved SP layout cannot describe both sides of a DP option.
    var text = String(opt || '');
    var layout = text.includes('/') ? null : savedLayout;
    return text.split(/(\s*[,/]\s*)/).map(function(part, index) {
        return index % 2 ? escapeLaneOptionText(part) :
            renderLaneOptionToken(part, layout) || escapeLaneOptionText(part);
    }).join('');
}
