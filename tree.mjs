import { JSDOM } from "jsdom";

// Create a simulated browser window and document
const dom = new JSDOM(`<!DOCTYPE html>`);
const document = dom.window.document;

// Your original code will now work perfectly:
const root = document.createElement("html");
root.lang = "en";

const head = document.createElement("head");
const title = document.createElement("title");
title.appendChild(document.createTextNode("My Document"));
head.appendChild(title);

const body = document.createElement("body");
const header = document.createElement("h1");
header.appendChild(document.createTextNode("Header"));
const paragraph = document.createElement("p");
paragraph.appendChild(document.createTextNode("Paragraph"));
body.appendChild(header);
body.appendChild(paragraph);

root.appendChild(head);
root.appendChild(body);

// Optional: Print the generated HTML to the console to verify
console.log(root.outerHTML);
