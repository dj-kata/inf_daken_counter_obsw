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
            var color = lane === '1' ? 'red' : Number(lane) % 2 === 0 ? 'blue' : 'white';
            return '<span class="lane-option-key lane-option-key-' + color + '">' + lane + '</span>';
        }).join('') + '</span>';
}

function renderLaneOptionChoice(token, savedLayout, originalHtml) {
    var numbers = renderLaneOptionToken(token, savedLayout);
    if (!numbers) return originalHtml;
    return '<span class="lane-option-choice"><span class="lane-option-original">' + originalHtml +
        '</span><span class="lane-option-numbers">' + numbers + '</span></span>';
}

function syncLaneOptionDisplay() {
    // URL settings are supplied by whole_layout.html; standalone views use CSS.
    var params = new URLSearchParams(window.location.search);
    var setting = params.has('show_lane_numbers') ? params.get('show_lane_numbers') :
        getComputedStyle(document.body || document.documentElement)
            .getPropertyValue('--show-lane-numbers').trim();
    document.documentElement.classList.toggle('lane-numbers-enabled', setting === '1');
}

document.addEventListener('DOMContentLoaded', syncLaneOptionDisplay);
setInterval(syncLaneOptionDisplay, 1000);

function renderLaneOption(opt, savedLayout) {
    // A single saved SP layout cannot describe both sides of a DP option.
    var text = String(opt || '');
    var layout = text.includes('/') ? null : savedLayout;
    return text.split(/(\s*[,/]\s*)/).map(function(part, index) {
        return index % 2 ? escapeLaneOptionText(part) :
            renderLaneOptionChoice(part, layout, escapeLaneOptionText(part));
    }).join('');
}
