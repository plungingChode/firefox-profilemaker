// Javascript to enable link to tab
const links = document.querySelectorAll(".nav a");
const active = { link: links[0].parentElement, form: document.getElementById("start") }
let old_hash = "";

function setActive(link, form) {
    active.link.classList.remove("active");
    active.form.classList.remove("active");

    link.classList.add("active");
    form.classList.add("active");
    
    active.link = link;
    active.form = form;
}

function showCurrentForm() {
    const id = location.hash || "#start";
    const form = document.getElementById(id.substr(1));

    for (const link of links) {
        if (link.href.endsWith(id)) {
            setActive(link.parentElement, form);
            break;
        }
    }
}

// Focus form after POST/hash change/nav link click. 
// Feels a little hacky, but I have no idea how to do it any other way
window.addEventListener("load", showCurrentForm);
window.addEventListener("hashchange", showCurrentForm);
links.forEach(l => l.addEventListener("click", showCurrentForm));

// Slightly faster alternative
/* links.forEach(l => {
    const href = l.href;
    const formName = href.substr(href.indexOf("#") + 1);

    const link = l.parentElement;
    const form = document.getElementById(formName);

    l.addEventListener("click", () => setActive(link, form));
}); */

const lightColors = {
    "--primary-main": "#00458B",
    "--primary-main-btn": "#00458B",
    "--primary-light": "#005dbb",
    "--primary-dark": "#013d79",

    "--secondary-main": "#fff44f",
    "--secondary-light": "#fff44f66",
    "--secondary-dark": "#766f00",

    "--neutral-main": " #959595",
    "--netural-light": "#a3a3a3",
    "--neutral-background-adjacent": "#f5f5f5",
    "--neutral-dark": "#7a7a7a",

    "--alert-main": "#8b0000",
    "--alert-light": "#a12b2b",
    "--alert-dark": "#720000",
    
    // Use RGB for dark mode preference detection
    "--background-color": "rgb(255, 255, 255)",
    "--text-color": "black",
};

const darkColors = {
    "--primary-main": "#ff4f5e",
    "--primary-main-btn": "#ee4a57",
    "--primary-light": "#f86975", 
    "--primary-dark": "#d4424e",
    
    "--secondary-main": "#fff44f",
    "--secondary-light": "#fff44f45",
    "--secondary-dark": "#fff34e",

    "--neutral-main": "#e7e5e2",
    "--neutral-dark": "#8d8c8c",
    "--neutral-background-adjacent": "#313131",

    "--alert-main": "#005e5e",
    "--alert-light": "#016e6e",
    "--alert-dark": "#004d4d",

    "--background-color": "#222222",
    "--text-color": "#e7e5e2",
};

const modeTransitions = [
    "background-color .5s ease-in",
    "color .5s ease-in",
    "border-color .5s ease-in",
    "fill .5s ease-in",
    "stroke .5s ease-in",
];

// inconclusive
// let darkMode = matchMedia("prefers-color-scheme: dark").matches

function isDarkMode() {
    const bodyBg = getComputedStyle(document.body, null)
        .getPropertyValue("background-color")
    const lightBg = lightColors["--background-color"];
    
    return bodyBg !== lightBg;
}

let darkMode = isDarkMode();

document
.getElementById("darkmode-toggle")
.addEventListener("click", () => {
    darkMode = !darkMode;
    const newColors = darkMode ? darkColors : lightColors;
    
    // Enable global transitions for the duration of the change
    const oldTransition = document.body.style.transition;
    document.body.style.transition = modeTransitions.join(",");
    setTimeout(() => document.body.style.transition = oldTransition, 510);

    for (const k in newColors) {
        document.body.style.setProperty(k, newColors[k]);
    }
});