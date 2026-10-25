// Used only by the desktop overlay. OBS pages keep their normal layout.
(() => {
    const content = document.getElementById('all');
    if (!content) return;
    const contentWidth = document.getElementById('results-tbody') ? 1600 : 1900;
    const style = document.createElement('style');
    style.textContent = `
        html, body { background: transparent !important; overflow: hidden !important; }
        body { margin: 0 !important; padding: 0 !important; }
        #all { width: ${contentWidth}px; max-width: none; margin: 0; transform-origin: top left; }
    `;
    document.head.appendChild(style);
    let pending = false;
    function fit() {
        if (pending) return;
        pending = true;
        requestAnimationFrame(() => {
            pending = false;
            const scale = Math.min(innerWidth / Math.max(content.offsetWidth, content.scrollWidth),
                                   innerHeight / Math.max(1, content.offsetHeight, content.scrollHeight), 1);
            content.style.transform = `scale(${scale})`;
        });
    }
    new MutationObserver(fit).observe(content, {childList: true, subtree: true, characterData: true});
    new ResizeObserver(fit).observe(content);
    window.addEventListener('resize', fit);
    if (document.fonts) document.fonts.ready.then(fit);
    fit();
})();
