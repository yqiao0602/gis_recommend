#!/usr/bin/env node
"use strict";

const fs = require("fs");

function fail(message) {
  console.error(message);
  process.exit(1);
}

const args = process.argv.slice(2);
if (args.length !== 2) {
  fail("Usage: node parse_gee_js_with_locations.js <input.js> <output_ast.json>");
}

let acorn;
try {
  acorn = require("acorn");
} catch (error) {
  fail(`acorn is not available: ${error.message}`);
}

const [inputFile, outputFile] = args;
let source;
try {
  source = fs.readFileSync(inputFile, "utf8");
} catch (error) {
  fail(`failed to read ${inputFile}: ${error.message}`);
}

if (source.charCodeAt(0) === 0xfeff) {
  source = source.slice(1);
}
if (source.startsWith("#!")) {
  source = `//${source.slice(2)}`;
}

let ast;
try {
  ast = acorn.parse(source, {
    ecmaVersion: 2020,
    sourceType: "script",
    allowReturnOutsideFunction: true,
    allowImportExportEverywhere: true,
    allowAwaitOutsideFunction: true,
    locations: true,
    ranges: true,
  });
} catch (error) {
  fail(`AST parse failed for ${inputFile}: ${error.message}`);
}

try {
  fs.writeFileSync(outputFile, JSON.stringify(ast, null, 2), "utf8");
} catch (error) {
  fail(`failed to write ${outputFile}: ${error.message}`);
}
