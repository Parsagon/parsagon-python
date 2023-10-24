window.prevDOM = null;
window.currentFieldType = null;
window.maxExamples = null;
window.disableAutocomplete = false;

const MOUSE_VISITED_CLASSNAME = 'parsagon-io-mouse-visited';
const TARGET_STORED_CLASSNAME = 'parsagon-io-example-stored';
const AUTOCOMPLETE_CLASSNAME = 'parsagon-io-autocomplete';

const OUTER_ACTIONS = ['button', 'a'];
const INNER_ACTIONS = ['span', 'img', 'svg', 'path', 'i', 'b', 'em', 'strong'];
const ACTION_EXCLUDES = [];
for (let outer of OUTER_ACTIONS) {
    for (let inner of INNER_ACTIONS) {
        ACTION_EXCLUDES.push(`${outer} ${inner}`);
    }
}

const DATA_TYPE_FILTERS = {
    TEXT: {
        includes: '*',
        excludes:
            'area, base, br, col, embed, hr, img, input, link, meta, param, source, track, wbr, template, script, style',
    },
    URL: { includes: 'a[href]', excludes: null },
    IMAGE: { includes: 'img[src], img[srcset]', excludes: null },
    HTML: { includes: '*', excludes: null },
    ACTION: { includes: '*', excludes: ACTION_EXCLUDES },
};

const CSS = `
* {
    pointer-events: auto;
}

.${MOUSE_VISITED_CLASSNAME} {
    outline: 1px solid rgb(51, 177, 255) !important;
    outline-offset: -1px !important;
}
.${MOUSE_VISITED_CLASSNAME}::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    height: 100%;
    width: 100%;
    outline: 1px solid rgb(51, 177, 255);
    outline-offset: -1px;
    z-index: 2147483647;
}

.${TARGET_STORED_CLASSNAME} {
    outline: 3px solid rgb(51, 177, 255) !important;
    outline-offset: -3px !important;
}
.${TARGET_STORED_CLASSNAME}::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    height: 100%;
    width: 100%;
    outline: 3px solid rgb(51, 177, 255);
    outline-offset: -3px;
    z-index: 2147483647;
}

.${AUTOCOMPLETE_CLASSNAME} {
    outline: 3px solid rgb(255, 177, 255) !important;
    outline-offset: -3px !important;
}
.${AUTOCOMPLETE_CLASSNAME}::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    height: 100%;
    width: 100%;
    outline: 3px solid rgb(255, 177, 255);
    outline-offset: -3px;
    z-index: 2147483647;
}
`;

function getRepresentative(element, dataType) {
    if (
        dataType === 'URL' ||
        dataType === 'IMAGE' ||
        dataType === 'HTML' ||
        dataType === 'ACTION'
    ) {
        return element;
    }

    let currentElement = element;
    while (true) {
        let parentElement = currentElement.parentElement;
        if (parentElement === null) {
            return currentElement;
        }

        if (currentElement.textContent !== parentElement.textContent) {
            return currentElement;
        }

        const currentRect = currentElement.getBoundingClientRect();
        const parentRect = parentElement.getBoundingClientRect();
        if (
            currentRect.bottom < parentRect.bottom ||
            currentRect.left < parentRect.left ||
            currentRect.top > parentRect.top ||
            currentRect.right > parentRect.right
        ) {
            return currentElement;
        }

        currentElement = parentElement;
    }
}

function hasValidData(element, dataType) {
    if (element == null) {
        return false;
    }
    if (dataType === 'TEXT' && typeof element.innerText === 'undefined') {
        return false;
    }
    return true;
}

function makeVisible(elements) {

    let elemsToDisplayBlock = [];
    for (let element of elements) {
        const rects = element.getClientRects();
        if (rects.length) {
            const rect = rects[0];
            if (rect.width * rect.height === 0) {
                elemsToDisplayBlock.push(element);
            }
        }
    }

    requestAnimationFrame(() => {
        for (let elem of elemsToDisplayBlock) {
            elem.style.display = 'block';
        }
    })
}

const DUMMY_FRAGMENT = document.createDocumentFragment()

function isValidSelector(selector) {
    try { DUMMY_FRAGMENT.querySelector(selector) } catch { return false }
    return true
}

function getSimilar(elements) {
    let tag = '*';
    if (elements.every((elem) => elem.tagName === elements[0].tagName)) {
        tag = elements[0].tagName.toLowerCase();
        tag = tag.replace(':', '\\:');
    }

    const classLists = elements.map((elem) => [...elem.classList]);
    const commonClasses = classLists
        .reduce((a, b) => a.filter((c) => b.includes(c)))
        .filter(
            (className) =>
                className !== TARGET_STORED_CLASSNAME &&
                className !== MOUSE_VISITED_CLASSNAME &&
                isValidSelector("." + className)
        )
        .map((className) => className.replace(':', '\\:').replace('.', '\\.').replace('[', '\\[').replace(']', '\\]').replace('=', '\\='));
    const classString = commonClasses.join('.');

    const siblingIndexes = elements.map(
        (elem) =>
            Array.prototype.indexOf.call(elem.parentNode.children, elem) + 1
    );
    let siblingIndex = null;
    if (siblingIndexes.every((index) => index === siblingIndexes[0])) {
        siblingIndex = siblingIndexes[0];
    }

    let elemString = tag;
    if (classString) {
        elemString += '.' + classString;
    }
    if (siblingIndex !== null) {
        elemString += `:nth-child(${siblingIndex})`;
    }

    const parentElements = elements.map((elem) => elem.parentElement);
    if (parentElements.some((elem) => elem === null)) {
        return elemString;
    } else {
        return `${getSimilar(parentElements)} > ${elemString}`;
    }
}

function addMouseVisitedCSS(element) {
    if (
        !element.classList.contains(TARGET_STORED_CLASSNAME) &&
        !element.classList.contains(AUTOCOMPLETE_CLASSNAME)
    ) {
        element.style.setProperty(
            'outline',
            '1px solid rgb(51, 177, 255)',
            'important'
        );
        element.style.setProperty('outline-offset', '-1px', 'important');
        if (
            window.getComputedStyle(element)
                .position === 'static'
        ) {
            element.style.setProperty('position', 'relative', 'important');
        }
    }
    element.classList.add(MOUSE_VISITED_CLASSNAME);
};
function removeMouseVisitedCSS(element) {
    if (
        !element.classList.contains(TARGET_STORED_CLASSNAME) &&
        !element.classList.contains(AUTOCOMPLETE_CLASSNAME)
    ) {
        element.style.removeProperty('outline');
        element.style.removeProperty('outline-offset');
        element.style.removeProperty('position');
    }
    element.classList.remove(MOUSE_VISITED_CLASSNAME);
};
function addTargetStoredCSS(element) {
    element.style.setProperty(
        'outline',
        '3px solid rgb(51, 177, 255)',
        'important'
    );
    element.style.setProperty('outline-offset', '-3px', 'important');
    if (
        window.getComputedStyle(element).position ===
        'static'
    ) {
        element.style.setProperty('position', 'relative', 'important');
    }
    element.classList.add(TARGET_STORED_CLASSNAME);
};
function removeTargetStoredCSS(element) {
    element.style.removeProperty('outline');
    element.style.removeProperty('outline-offset');
    element.style.removeProperty('position');
    element.classList.remove(TARGET_STORED_CLASSNAME);
    if (element.classList.contains(AUTOCOMPLETE_CLASSNAME)) {
        addAutocompleteCSS([element]);
    } else if (element.classList.contains(MOUSE_VISITED_CLASSNAME)) {
        addMouseVisitedCSS(element);
    }
};
function addAutocompleteCSS(elements) {
    let setOutlineElements = [];
    let makeStaticElements = [];
    for (const element of elements) {
        if (!element.classList.contains(TARGET_STORED_CLASSNAME)) {
            setOutlineElements.push(element);
            if (
                window.getComputedStyle(element)
                    .position === 'static'
            ) {
                makeStaticElements.push(element);
            }
        }
    }

    // Perform batch writes
    requestAnimationFrame(() => {
        for (const element of setOutlineElements) {
                element.style.setProperty(
                'outline',
                '3px solid rgb(255, 177, 255)',
                'important'
            );
            element.style.setProperty('outline-offset', '-3px', 'important');
        }
        for (const element of makeStaticElements) {
            element.style.setProperty('position', 'relative', 'important');
        }
        for (const element of elements) {
            element.classList.add(AUTOCOMPLETE_CLASSNAME);
        }
    });
};

function removeAutocompleteCSS(element) {
    element.style.removeProperty('outline');
    element.style.removeProperty('outline-offset');
    element.style.removeProperty('position');
    element.classList.remove(AUTOCOMPLETE_CLASSNAME);
    if (element.classList.contains(MOUSE_VISITED_CLASSNAME)) {
        addMouseVisitedCSS(element);
    }
};

function getNumExamples() {
    const exampleElems =
        document.getElementsByClassName(
            TARGET_STORED_CLASSNAME
        );
    return exampleElems.length;
};

function addAutocompletes() {
    const autocompleteElems =
        document.getElementsByClassName(
            AUTOCOMPLETE_CLASSNAME
        );
    while (autocompleteElems.length) {
        removeAutocompleteCSS(autocompleteElems[0]);
    }

    const exampleElems =
        document.getElementsByClassName(
            TARGET_STORED_CLASSNAME
        );
    if (exampleElems.length) {
        const cssSelector = getSimilar([...exampleElems]);
        const similarElems =
            document.querySelectorAll(
                cssSelector
            );

        // Set to similarElems where elem.classList.contains(TARGET_STORED_CLASSNAME) === false
        const elemsToMakeVisibleAndAddAutocompleteCSS = Array.from(similarElems).filter((elem) => {
            return !elem.classList.contains(TARGET_STORED_CLASSNAME);
        });
        makeVisible(elemsToMakeVisibleAndAddAutocompleteCSS);
        addAutocompleteCSS(elemsToMakeVisibleAndAddAutocompleteCSS);
    }
};

function clearCSS() {
    const highlightedElems =
        document.querySelectorAll(
            "." + MOUSE_VISITED_CLASSNAME
        );
    for (const elem of highlightedElems) {
        removeMouseVisitedCSS(elem);
    }

    const autocompleteElems =
        document.querySelectorAll(
            "." + AUTOCOMPLETE_CLASSNAME
        );
    for (const elem of autocompleteElems) {
        removeAutocompleteCSS(elem);
    }

    const exampleElems =
        document.querySelectorAll(
            "." + TARGET_STORED_CLASSNAME
        );
    for (const elem of exampleElems) {
        removeTargetStoredCSS(elem);
    }
}

function handleAutocomplete() {
    if (window.currentFieldType === null) {
        return;
    }

    const autocompleteElements =
        document.querySelectorAll(
            `.${AUTOCOMPLETE_CLASSNAME}`
        );

    for (const elem of autocompleteElements) {
        removeAutocompleteCSS(elem);
        addTargetStoredCSS(elem);
    }
};

function handleClick(e) {
    if (window.currentFieldType === null) {
        return;
    }

    e.preventDefault();
    e.stopImmediatePropagation();

    const srcElement = document.querySelector(
        `.${MOUSE_VISITED_CLASSNAME}`
    );
    if (srcElement === null) {
        return;
    }

    if (srcElement.classList.contains(TARGET_STORED_CLASSNAME)) {
        removeTargetStoredCSS(srcElement);
        if (!window.disableAutocomplete) {
            try {
                addAutocompletes();
            } catch (e) {
                console.log(e);
                // carry on even if autocomplete runs into invalid CSS classes/IDs
            }
        }
    } else {
        if (
            window.maxExamples &&
            getNumExamples() >= window.maxExamples
        ) {
            return;
        }
        addTargetStoredCSS(srcElement);
        if (!window.disableAutocomplete) {
            try {
                addAutocompletes();
            } catch (e) {
                console.log(e);
                // carry on even if autocomplete runs into invalid CSS classes/IDs
            }
        }
    }
};

function handleMouseDown(e) {
    if (window.currentFieldType === null) {
        return;
    }

    e.preventDefault();
    e.stopImmediatePropagation();
};

function handleMouseMove(e) {
    if (window.currentFieldType === null) {
        return;
    }

    e.preventDefault();
    e.stopImmediatePropagation();

    if (
        window.maxExamples &&
        getNumExamples() >= window.maxExamples
    ) {
        return;
    }

    if (window.prevDOM != null) {
        removeMouseVisitedCSS(window.prevDOM);
    }

    let candidates =
        document.elementsFromPoint(
            e.clientX,
            e.clientY
        );
    if (['URL', 'IMAGE'].includes(window.currentFieldType)) {
        const newCandidates = new Set();
        for (const elem of candidates) {
            let closest = null;
            if (window.currentFieldType === 'URL') {
                closest = elem.closest('a');
            } else if (window.currentFieldType === 'IMAGE') {
                closest = elem.querySelector('img');
            }
            if (closest) {
                newCandidates.add(closest);
            }
        }
        candidates.push(...newCandidates);
    }
    candidates = [...candidates].filter((elem) => {
        if (
            !elem.matches(
                DATA_TYPE_FILTERS[window.currentFieldType].includes
            )
        ) {
            return false;
        }
        if (elem.offsetHeight * elem.offsetWidth === 0) {
            if (elem.tagName === 'A') {
                elem.style.display = 'inline-block';
            } else {
                return false;
            }
        }

        const rect = elem.getBoundingClientRect();
        if (
            e.clientX < rect.left ||
            e.clientX > rect.right ||
            e.clientY < rect.top ||
            e.clientY > rect.bottom
        ) {
            return false;
        }

        return true;
    });
    if (DATA_TYPE_FILTERS[window.currentFieldType].excludes) {
        candidates = candidates.filter(
            (elem) =>
                !elem.matches(
                    DATA_TYPE_FILTERS[window.currentFieldType].excludes
                )
        );
    }
    if (!candidates.length) {
        return;
    }
    candidates.sort(
        (a, b) =>
            a.offsetHeight * a.offsetWidth - b.offsetHeight * b.offsetWidth
    );

    const srcElement = getRepresentative(
        candidates[0],
        window.currentFieldType
    );
    if (!hasValidData(srcElement, window.currentFieldType)) {
        return;
    }

    makeVisible([srcElement]);

    addMouseVisitedCSS(srcElement);
    window.prevDOM = srcElement;
};

function handleSelectionShift() {
    if (window.currentFieldType === null) {
        return;
    }
    if (window.prevDOM != null && window.prevDOM.parentElement) {
        removeMouseVisitedCSS(window.prevDOM);
        addMouseVisitedCSS(window.prevDOM.parentElement);
        window.prevDOM = window.prevDOM.parentElement;
    }
}

function handleKeyDown(e) {
    if (window.currentFieldType === null) {
        return;
    }

    e.preventDefault();
    e.stopImmediatePropagation();

    const key = e.key;
    if (key === "Backspace" || key === "Delete") {
        clearCSS();
    }
    if (key === "Tab") {
        handleAutocomplete();
    }
    if (key === "Control") {
        handleSelectionShift();
    }
    if (key === "Alt") {
        window.disableAutocomplete = true;
    }
}

function handleKeyUp(e) {
    if (window.currentFieldType === null) {
        return;
    }

    e.preventDefault();
    e.stopImmediatePropagation();

    const key = e.key;
    if (key === "Alt") {
        window.disableAutocomplete = false;
    }
}

if (!window.PSGN_INITIALIZED) {
    window.PSGN_INITIALIZED = true;
    const style = document.createElement('style');
    document.head.appendChild(style);
    style.type = 'text/css';
    const text = document.createTextNode(CSS);
    style.appendChild(text);

    window.addEventListener(
        'mousemove',
        handleMouseMove,
        true
    );

    window.addEventListener(
        'click',
        handleClick,
        true
    );

    window.addEventListener(
        'mousedown',
        handleMouseDown,
        true
    );

    window.addEventListener(
        'keydown',
        handleKeyDown,
        true
    );

    window.addEventListener(
        'keyup',
        handleKeyUp,
        true
    );

    window.clearCSS = clearCSS;
}
