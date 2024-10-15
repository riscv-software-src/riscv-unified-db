const asciidoctor = require('asciidoctor')()
const registry = asciidoctor.Extensions.create()
require('./asciidoc_when_extension.js')(registry)