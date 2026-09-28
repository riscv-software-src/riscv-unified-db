# Programmable RISC-V IDE (PRIDE) Developer Guide

*Authors: Brayden Mendoza (brayjmendoza), Nina Luo (niluo-shiqi)*
*Last Edited: August 29th, 2026*

## Overview

PRIDE is implemented using [Xtext](https://eclipse.dev/Xtext/documentation/), an Eclipse framework used for developing domain-specific languages (DSL). Thus, contributing to this project requires using the Eclipse IDE with Xtext installed. Moreover, this project is more accurately a DSL project rather than an IDE project. We have given this DSL the name "UDB", which uses the `.udb` file extension. So, to get access to any features of PRIDE, you must use `.udb` files (and not `.yaml`).

With Xtext, we just have to specify a grammar and all of the IDE features will be generated for us (in particular, syntax highlighting, syntax errors, and cross-referencing). However, we can further customize what Xtext generates with some additional code. It should be noted that Xtext by default only generates IDE features for Eclipse. Luckily, Xtext is compliant with the Language Server Protocol (LSP), meaning that we can very easily generate a language server, which can then be used to support other IDEs (we currently support VSCode with our [UDB Schema Editor extension](https://marketplace.visualstudio.com/items?itemName=HarveyMuddClinicTeam.udb-schema-editor)).

So, at a high level, developing PRIDE involves modifying the files in the Xtext project (primarily the grammar file and validator) to create new features. Then, you would then generate a new language server to update support in other IDEs. The rest of this markdown file will go into much greater detail of everything involved in this project.

## Table of Contents

- [Getting Started](#getting-started)
- [The Grammar](#the-grammar)
  - [Structure](#structure)
  - [Whitespace Awareness](#whitespace-awareness)
- [The Validator](#the-validator)
  - [Structure](#structure-1)
  - [ISA Description Language (IDL) at Runtime](#isa-description-language-idl-at-runtime)
- [Customizing Xtext Components](#customizing-xtext-components)
  - [Cross-Referencing](#cross-referencing)
  - [Hex and Binary](#hexadecimal-and-binary)
- [Maven](#maven)
  - [High Level Structure](#high-level-structure)
  - [Incorporating IDL at Build Time](#incorporating-idl-at-build-time)
- [JUnit Testing](#junit-testing)
  - [Continuous Integration](#continuous-integration)
- [The Language Server](#the-language-server)
- [Converting Between YAML and UDB](#converting-between-udb-and-yaml)
  - [Using the Conversion Script](#using-the-conversion-script)
  - [Modifying the Conversion Script](#modifying-the-conversion-script)
- [Other Notes & Quirks](#other-notes--quirks)

---

## Getting Started

To begin development with this project, first download Eclipse with Xtext. For a fresh install, download the "Eclipse IDE for Java and DSL Developers" found [here](https://www.eclipse.org/downloads/packages/). If you already have Eclipse installed, you can find more instructions [here](https://eclipse.dev/Xtext/download.html). Be sure to have GitHub set up with Eclipse.

Now, in a fresh workspace, import this repository. To do so, click Import projects (found under Package or Project Explorer), then click Git -> Projects with Git (with smart import). Then choose your repository source. Before clicking finish, I would recommend deselecting the root of this repository (i.e., `riscv-unified-db`). This is because the entire Xtext project is contained within `tools/eclipse/dev/org.xtext.udb.parent`. We've personally had issues with Eclipse when we imported the entire `riscv-unified-db` repository, and found that excluding the root prevented them.

Next, navigate to the [GenerateUdb.mwe2](dev/org.xtext.udb.parent/org.xtext.udb/src/org/xtext/example/udb/GenerateUdb.mwe2) file found in the `org.xtext.udb` package. Right click this file in the project explorer and press Run As -> MWE2 Workflow. This workflow is what Xtext uses to generate all of the artifacts of the project, including the IDE features. When you first run it, Eclipse will mention how there are errors in the project. This is expected, press Proceed. This process may take some time. If you run into issues, in the project explorer right click on the `org.xtext.udb.parent` directory and press Maven -> Update Project (this will definitely take some time). Now, run the MWE2 workflow again.

 Once everything has generated, you should now be able to use the IDE features in Eclipse! In the project explorer, right click on `org.xtext.example.udb` (the package that contains the MWE2 workflow), and press Run As -> Eclipse Application. This will open a new instance of Eclipse that you can use to test out the features of PRIDE. First, create a new general project, and then create a new file with the `.udb` file extension. Eclipse will then ask you if you would like to convert the project into an Xtext project. Click yes, and you're all set!

---

## The Grammar

The grammar is a `.xtext` file that defines allowable syntax. This defined syntax is YAML-like, to match the `.yml` files of RISC-V specifications. Thus, the Xtext grammar serves as a YAML parser for RISC-V specifications.

**NOTE:** In terms of language development, you can think of the grammar as the component that handles syntax.

### Location

The grammar file can be found [here](dev/org.xtext.udb.parent/org.xtext.udb/src/org/xtext/example/udb/Udb.xtext) (`tools/eclipse/dev/org.xtext.udb.parent/org.xtext.udb/src/org/xtext/example/udb/Udb.xtext`).

### Structure

The start of the file begins with the parent rule of the grammar, `Model`, which lists all of the currently supported schemas. Then, we have rules for each of these schemas, which serve as the parent rule for their own respective grammars. Next, there's a chunk of code that contains grammar snippets that are commonly used across multiple schemas.

Then, we have the grammars for each of the schema's, written in the order they are listed in `Model`. This is the bulk of the file. To modify the grammars of existing schemas, you will want to change/add code in this section.

Finally, we have the grammar for conditions, which is currently commented out for reasons explained below. The rest of the file contains terminals and helper rules which are not tied to any particular schema.

In general, if you would like to add support for a new schema, just follow the examples found in the `.xtext` file. Using the CSR schema as an example, we can see that the it is listed in `Model`, and then later the `CsrModel` rule is defined (this is the parent rule for the schema). This rule uses a bunch of CSR-specific grammar rules that are all defined further down the file. These are obvious as they are all prefixed with `Csr`, except for the commonly used rules. When developing new schemas or modifying existing ones, please follow this structure and maintain the existing code style.

**IMPORTANT NOTE:** The first two grammar rules of every schema must be Schema and Kind (in that order). Using CSR as an example, you can see that in the definition for `CsrModel`, the first rule is `Schema` and the second is `CsrKind`. This is important as this is what allows the resulting IDE to determine which schema the RISC-V specification should be following. Note that this means that all `.udb` files must start with the `$schema` and `kind` fields (everything else can be unordered).

### Whitespace Awareness

By default, Xtext grammars are not whitespace aware. So, to make the grammar YAML-like, we added synthetic `INDENT` and `DEDENT` tokens to keep track of indentations. However, to get Xtext to use these tokens to enforce indentations, we modified [UdbTokenSource.java](dev/org.xtext.udb.parent/org.xtext.udb/src/org/xtext/example/udb/parser/antlr/UdbTokenSource.java) in the `org.xtext.example.udb.parser.antlr` package. By overriding some functions, we were able to attain whitespace awareness.

### Note on Conditions

We do currently have a grammar implemented for conditions (see "conditions" in [schema_def.json](../../spec/schemas/schema_defs.json) for the official definition). However, we have found that this causes issues with syntax errors (see our [GitHub issue](https://github.com/niluo-shiqi/riscv-unified-db-hmc-clinic-team-/issues/4)). Since highlighting syntax errors is a very major and useful IDE feature, we decided to comment out this portion of the grammar. Until a solution has been implemented, we have replaced this grammar to just accept a simple string.

### Note on IDL
Our Xtext DSL and IDE does support IDL, though it's grammar is defined elsewhere in a Ruby treetop grammar. See [ISA Description Language (IDL)](#isa-description-language-idl) for more details.

---

## The Validator

The validator is a key component of any Xtext project whose purpose is to enforce constraints on the grammar. For example, the `CsrLength` rule accepts integers. However, the CSR schema specifies that if the length is an integer, then it's value must be either 32 or 64. To encode this requirement of the schema, we can create a function in the validator to enforce this constraint in the grammar. If a user were to violate one of these rules, they would see it as a syntax error in the IDE with a custom error message we specify.

**NOTE:** In terms of language development, you can think of the validator as the component that handles semantics.

### Location

The validator file can be found [here](dev/org.xtext.udb.parent/org.xtext.udb/src/org/xtext/example/udb/validation/UdbValidator.java) (`tools/eclipse/dev/org.xtext.udb.parent/org.xtext.udb/src/org/xtext/example/udb/validation/UdbValidator.java`).

### Structure

Just like the grammar file, the validator is largely organized by schema. At the top of the file, there are a large number of imports. The majority of these correspond to rules in the grammar and are thus organized by schema.

The rest of the file consists of a Java class, which defines the validator. This class contains all of the functions which define the constraints of the grammar as defined in each specification's JSON schema. Also, note that the beginning of this class contains a bunch of regex's that are commonly used throughout the validator. The majority of these were taken directly from [schema_defs.json](../../spec/schemas/schema_defs.json). Just like how the grammar rules were separated by schema, the validator functions are also separated by schema. After the validators for the schemas, we have a section for validating *general* fields, that is, those that are often used across multiple schemas.

It should be noted that this file also contains a validator for conditions. However, since we currently are not using the conditions grammar (see our [GitHub issue](https://github.com/niluo-shiqi/riscv-unified-db-hmc-clinic-team-/issues/4)), these functions remain unused at runtime.

Finally, at the end of the class we have functions that allow compatibility with IDL. These functions take in an IDL snippet, send it off to ruby, then throws an error if the snippet has syntax errors. This mechanism is described in detail [below](#isa-description-language-idl-at-runtime).

In general, all of the functions in the validator just enforce a rule found in a specification's schema (this includes those found in [schema_defs.json](../../spec/schemas/schema_defs.json)).

### ISA Description Language (IDL) at Runtime

ISA Description Language (IDL) is another domain-specific language that was created to aid with RISC-V specification development. Many schemas have fields whose values are IDL snippets. So, to add support for IDL in PRIDE, IDL has become a subset of the larger UDB DSL we have implemented with Xtext.

IDL was originally implemented with Treetop, a Ruby-based tool that can be used to create DSL's. IDL is currently packaged as a ruby gem found [here](../../tools/ruby-gems/idlc/), known as `idlc`. IDL is defined by as a parser expression grammar and already has features like type-checking. To take advantage of the work that has already been done, we incorporated IDL into PRIDE by using JRuby, which serves as a Ruby interpreter that runs within Java.

The incorporation of IDL into the Xtext project is quite complex. At a high level, first, at build time the IDL Ruby gem is copied into the Xtext project. Then, at runtime, a Ruby environment that allows us to use the `idlc` gem is setup first. Then, IDL snippets are passed into the validator, and JRuby uses the `idlc` gem alongside the IDL code to determine if the input is valid. Finally, if an error is detected, it is returned and shown to the user.

Setting up the Ruby environment makes heavy use of Maven, which will be discussed further [below](#incorporating-idl-at-build-time). This section will delve into using the validator to validate IDL snippets. The validator class instantiates a `TreetopParser` object, which is defined in [TreetopParser.java](dev/org.xtext.udb.parent/org.xtext.udb/src/org/xtext/example/udb/treetop/TreetopParser.java), which is found in the `org.xtext.example.udb.treetop` package. This class has a `parse` method. This is the function that the validator uses to hand off IDL snippets to Ruby to determine if there are any errors. `parse` takes in two arguments: the IDL snippet (as a string) and the IDL grammar rule that Ruby should start parsing from. If only one parameter is given, the function will assume that the input string is IDL code and that it should start parsing from the grammar's default root rule. `parse` returns a `ValidationError`, which is defined in [ValidationError.java](dev/org.xtext.udb.parent/org.xtext.udb/src/org/xtext/example/udb/treetop/ValidationError.java), which also exists in the `org.xtext.example.udb.treetop` package. In short, this `ValidationError` just formats and creates the error message that the user will see if their specification contains incorrect IDL code.

Determining what the root grammar rule of an IDL snippet should be requires digging through some code. In particular explore, [this directory](../ruby-gems/udb/lib/udb/) (`tools/ruby-gems/udb/lib/udb/`). For the most part, we have found everything we needed in `obj/`. This directory contains a number of Ruby files that correspond to different schemas (for the most part). Let's use CSR as an example. CSR has a `sw_read()` field that takes in IDL. To determine what the root rule should be, I would first go into the [obj/csr.rb](../ruby-gems/udb/lib/udb/obj/csr.rb) file, and find a function called something along the lines of `sw_read_ast` (i.e., the name of the field followed by `ast`). Indeed, on line 518 we can find a function named `sw_read_ast`. Now, I would look for the line that looks like its doing some parsing. Luckily, there is a useful comment on line 524 that tells us the following line will parse. On line 525, we find a call to `idl_compiler.compile_func_body(...)`. This name is descriptive, as it indicates that to parse the IDL snippet that gets parsed into `sw_read()`, we should start from the `function_body` grammar rule. In general, you would want to find a call to `idl_compiler.compile_GRAMMAR_RULE`. Here, `GRAMMAR_RULE` is the root rule we should pass into the `parse` function. Note that in this case, `func_body` isn't one-to-one with the actual grammar rule name (`function_body`). This isn't always the case, but it should still be pretty clear what grammar rule the `idl_compiler` function call is referring to. For a complete list of the possible IDL grammar rules, please see the [IDL grammar file](../ruby-gems/idlc/lib/idlc/idl.treetop) (`tools/ruby-gems/idlc/lib/idlc/idl.treetop`).

In general, all IDL fields must go through the validator. Please do use pre-existing IDL-related validator functions as reference when adding new ones. Each of these functions should all have the same structure.

---

## Customizing Xtext Components

Though PRIDE is inherently an IDE project, by using Xtext we are more accurately creating a domain-specific language (DSL). As mentioned previously, given a grammar Xtext will generate IDE features. However, as a framework for DSL's, Xtext does this by generating all of the components that go into a language. These include a lexer, parser, the actual IDE features, and much, much more.

Sometimes, what Xtext generates by default does quite do what we want it to. Luckily, we can customize these generated components (for the most part). In general, customizing Xtext components involves subclassing the class that Xtext generates, overriding necessary functions, and then registering the subclass in `UdbRuntimeModel.java`. The rest of this section details every instance where we've had to do this so far.

### Cross-Referencing

Mention [UdbQualifiedNameProvider.java](dev/org.xtext.udb.parent/org.xtext.udb/src/org/xtext/example/udb/naming/UdbQualifiedNameProvider.java) and why we need it and  then registering it in [UdbRuntimeModule.java](dev/org.xtext.udb.parent/org.xtext.udb/src/org/xtext/example/udb/UdbRuntimeModule.java)

### Hexadecimal and Binary

At the end of the `.xtext` file, there is a small chunk of code that defines a grammar for representing integers in either hexadecimal or binary. However, defining the grammar alone will not get Xtext to recognize hex and binary as legitimate integers. So, we created [UdbValueConverter.java](dev/org.xtext.udb.parent/org.xtext.udb/src/org/xtext/example/udb/UdbValueConverter.java). This file contains a class that subclasses Xtext's generated class that handles value conversion. The subclass then overrides some functions to allow conversion from hexadecimal and binary to integers in decimal form. We then register this class in [UdbRuntimeModule.java](dev/org.xtext.udb.parent/org.xtext.udb/src/org/xtext/example/udb/UdbRuntimeModule.java), so that at runtime hex and binary can be interpreted as actual integers. This proves useful for validation and testing.

---

## Maven

Maven is the Java build management tool that is used for this Xtext project. It handles things like configuration files and dependency management, and for the most part is something you'll never have to think about. However, it's good to understand to some degree what Maven is doing in case you need to do something like add a dependency. Indeed, when incorporating IDL into PRIDE, we had to add JRuby as a dependency. To do so required us to modify how Maven builds the project.

### High Level Structure

This Xtext project is built with Maven. Thus, the parent package (`org.xtext.udb.parent`) is a Maven project that consists of several Maven modules. You can think of this parent package as a larger multi-module build that contains all of the packages in the project. Each module contains `MANIFEST.MF`, `build.properties`, and `pom.xml` files that allow Maven to automate the building process. `MANIFEST.MF` defines how Java executes and handles the package while `build.properties` exposes build metadata at runtime. Most importantly, `pom.xml` acts as the single source of truth and tells Maven what the project is, how to build it, and what external libraries it needs. It's not imperative that you deeply understand how Maven works, as these files are largely generated. This information proves most useful when adding additional Maven modules to the Xtext project, which we suspect will not happen often if at all. The remainder of this section will highlight the only time we've had to do this so far: incorporating IDL.

### Incorporating IDL at Build Time

As mentioned previously, IDL is packaged as a Ruby gem. Thus, to make use of this gem in a Java project, we needed to use JRuby, which allows us to run Ruby scripts in a Java project. This involves adding JRuby as a dependency to the project. So, we must turn to Maven and customize how it builds the project.

Since JRuby isn't typically a dependency in Xtext projects, we ultimately found that we had to create a new Maven module to add this dependency. In particular, we created the Maven module `org.xtext.udb.jruby` to act as a wrapper (more specifically, an OSGi wrapper bundle) that exposes JRuby to the rest of the project. This module also contains the file [RubyRuntime.java](dev/org.xtext.udb.parent/org.xtext.udb.jruby/src/org/xtext/udb/jruby/RubyRuntime.java), which runs a Ruby script to setup the Ruby environment that lets us use `idlc`. This script is run at runtime, but for it to run successfully certain things need to happen first (during build time).

The Ruby script assumes that `bundler`, a Ruby package manager, is installed and that it has access to `idlc`. To ensure that these assumptions are met, we can modify the `pom.xml` found in this `org.xtext.udb.jruby` Maven module. In this file, we can specify actions that Maven should perform when building the project. To
satisfy the script's conditions, we first copy the `.jar` files for a number of dependencies (including JRuby) into the module (more specifically, they are copied into `lib/`). This process is defined in lines 60-115 of the `pom.xml`. Then, we copy the entire `idlc/` directory from `ruby-gems` into the module (see lines 116-140). Java will not access files out of its own project, so we must copy `idlc/` so that we don't run into permission issues. Finally, we use the JRuby `.jar` file we copied earlier to run some Ruby commands that install and configure bundler in a way that allows the Ruby script to run (see lines 142-238).

Now, at build time, Maven will perform the actions detailed above. In fact, the commands that install bundler are why rebuilding/updating the project with Maven takes some time. At runtime, the Ruby script in `RubyRuntime.java` is run, giving us IDL compatability with PRIDE!

**NOTE:** You may notice the `vendor/` directory. This is generated by the script run in `RubyRuntime.java` and is used to store all of the dependencies for `idlc/`.

---

## JUnit Testing

One way we've tested our Xtext DSL is with JUnit tests. In short, all tests for Xtext projects exist in either the `org.xtext.udb.tests` or `org.xtext.udb.tests.ui` packages. In particular, `org.xtext.udb.tests` should contain all grammar-related tests. Thus, these tests can test components like the parser, lexer, validator, etc. These tests run as normal JUnit tests. On the other hand, the `org.xtext.udb.tests.ui` should only contain UI-related tests. These can be used to test things like syntax highlighting, auto-completion, quick fixes, etc. Unlike in `org.xtext.udb.tests`, these tests should be run as JUnit Plug-in tests.

Currently, we've only done testing in the `org.xtext.udb.tests` package. They all exist in the file [UdbParsingTest.xtend](dev/org.xtext.udb.parent/org.xtext.udb.tests/src/org/xtext/example/udb/tests/UdbParsingTest.xtend). To run these tests, simply right click the file in Eclipse's Project Explorer, and press Run As -> JUnit Test. You may notice that currently, there are very few tests. Thus, the project doesn't have a very good testing coverage. This is because (for better or for worse) we've typically done our testing by running the IDE in an Eclipse Runtime instance and fixing any bugs we find.

It should be noted that these JUnit tests are written in Xtend ([documentation here](https://eclipse.dev/Xtext/xtend/documentation/index.html)). This programming language is a dialect of Java which is more flexible and statically-typed. You can think of it as a more modern version of Java.

## Continuous Integration

All of our JUnit tests have been incorporated into the standard CI workflow. This additionally includes headless VSCode Extension tests ensuring a valid language server and thus VSCode Extension can be generated with the current state of the grammar in the repository.

### Test Stack

- **Framework**: Mocha (see `package.json` line 176)
- **VS Code Testing**: @vscode/test-electron (headless testing)
- **Language**: TypeScript (compiled to JavaScript for execution)

### CI Tests Structure

Under .github/workflow/
- regress.yml: Github Actions Pipeline, runs Xtext JUnit tests and headless VSCode tests
Under /udb-vscode/
- Package.json: packages, terminal command to run tests:
- Tsconfig.json: typescript configurations
Under src/test/
- runTests.ts: script which runs tests for test-fixtures
Under /suite
- index.ts: consolidates and simplifies exports and imports
- basic.test.ts: Main Testing File (Mocha tests are written here)
Under test-fixtures/
- Valid test cases of actual example files
  - A.udb,
  - vsstatus.udb,
  - andn.udb
- Error test cases of actual example files
  - AErr.udb,
  - andnErr.udb,
  - vsstatusErr.udb

### Running Tests Locally
To run the VS Code tests on your machine:
```bash
npm install
npm test
```

### Triggered upon
The `regress.yml` workflow is triggered on:
- Pull requests to `main`
- Pushes to `main`
- Manual workflow dispatch

### Troubleshooting Tests

- **Tests fail locally but pass in CI**: Ensure you're using the correct Node version (24.18.0 as specified in `package.json`)
- **VSCode display errors**: The CI pipeline runs tests headless using `xvfb-run` on Linux
- **Compilation fails**: Run `npm run compile` or `aube run compile` before testing

### Adding New Test Cases

1. Create a new `.udb` file in `test-fixtures/`
2. Add corresponding test logic in `src/test/suite/basic.test.ts`
3. Tests will automatically pick up the new fixture file
4. For error cases, follow the naming pattern: `{name}Err.udb`


---

## The Language Server

Instead of writing a custom plugin for every single editor (like VS Code, Eclipse, or IntelliJ), Xtext allows you to build your language logic once by providing the easy generation of a Xtext Language Server for your written DSL. The generated language server then communicates with the alternative code editors using Microsoft’s Language Server Protocol (LSP). In other words, to use a DSL created with Eclipse Xtext in another IDE (such as VSCode), we generate the language server encapsulating the core features of the DSL and package it within the other IDE's extension wrapper. Let's begin by generating the language server itself, note that every time the DSL gets updated or modified, the language server would need to be regenerated in the same way, which indeed also means that the extension would need to be repackaged with the new language server as well:

### Generating/Regenerating the Language Server

### Prerequisites
Pull the repository into your local editor.

### macOS

Run the following commands in your terminal to generate the jar file and Ruby dependencies in the correct location:

```bash
chmod +x tools/scripts/language-server-script/regen-udb-ls.sh
./tools/scripts/language-server-script/regen-udb-ls.sh
```

> **Note:** The `chmod` command only needs to be run once per session.

### Windows

Run the following command in your terminal to generate the jar file and Ruby dependencies in the correct location:

```bash
tools\scripts\language-server-script\regen-udb-ls.bat
```

### Expected Output
After running the script, you should see the following in `/tools/eclipse/udb-vscode/server`:
- `udb-ls-all.jar`
- `idlc` folder
- `vendor` folder

### Simulating the Extension (Packaged Language Server) in VSCode

The VSCode Extension Wrapper consists of multiple files all within the folder `tools/eclipse/udb-vscode`:

#### Required Files (for publishing/runtime)
- `package.json` — VS Code extension manifest, scripts, and dependency metadata
- `language-configuration.json` — editor language settings (comments, brackets, auto-closing)
- `syntaxes/udb.tmLanguage.json` — TextMate grammar for UDB syntax highlighting

#### Recommended Files (for distribution)
- `README.md` — user-facing documentation and usage instructions
- `LICENSE.txt` — project license text

#### Configuration & Build Files
- `.vscode/` — editor workspace settings and debug configurations for development
- `.vscodeignore` — patterns to exclude from the packaged VSIX
- `aube-workspace.yaml` — Aube build/workspace configuration (development/build helper)
- `package-lock.json` — npm lockfile for reproducible installs
- `tsconfig.json` — TypeScript compiler configuration for building the extension

#### Development Files (source code)
- `src/extension.ts` — TypeScript implementation of the extension and language-client setup
- `src/extension.js` — compiled JavaScript runtime (published package must include at path declared in `package.json`)
- `src/extension.d.ts` & `.map` files — type declarations and source maps for debugging
- `src/test/` — test harness and tests

#### Documentation & Examples
- `CHANGELOG.md` — release notes and version history
- `test-fixtures/` — example files used by tests or as examples

#### Important Note: Language Server

The language server jar file is **NOT** pushed to the GitHub repository due to its large size. It can be generated quickly and easily using the provided build script (see section above). Once generated, the language server and its associated `idlc` and `vendor` folders will be located in a new `server/` directory under `udb-vscode/`. Once present, the extension is complete and ready to use.

### Prerequisites
Pull the repository with the complete packaged extension into your local VSCode Editor.

Open the folder udb-vscode/ in VSCode (located under the root directory but make sure to not open the entire root directory).

Note that at this point, udb-vscode should contain the server folder with the .jar file, idlc, and vendorfolders.

Open a new terminal and run the following commands:
- `cd Udb-vscode`
- `npm install`
- `npm run compile`

Open the Run & Debug panel on the left hand side of VSCode

Choose Run Extension and start (This will open the Extension Development Host, which appears as a new VSCode window)

On your very first run, make sure you point to Java 21, in the top menu of VS Code, select:
Code>Settings>Settings
Search “UDB: Java Path”
For me, I filled in the Java Path as: (I’m on mac, this may be different for you)
- `/Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents/Home/bin/java`

If you don’t have a mac/just check path to make sure, this should give you your path(make sure you use the 21 version)
/usr/libexec/java_home -V

Now, in the Extension Development Host window, create a new udb file by going to File>New File>, then enter any file name ending in .udb (like “test.udb”).

Try typing in this file. If you see the csr class being suggested and red squiggles under invalid grammar, your VSCode extension is working.

If you do not see the grammar functionality showing up, check the messages within the error logs to narrow down the exact cause.

---

## Converting Between UDB and YAML

YAML allows string values that are unquoted. However, Xtext requires its strings to be quoted. We've tried to customize Xtext's lexer to allow for unquoted strings, but we ultimately found this to be way too difficult and that it'd cause some problems that'd be unreasonable to attend to. Thus, **UDB is not currently one-to-one with YAML.** That is, you cannot simply change the file extension of a RISC-V specification from `.yaml` to `.udb` to get access to all of the features of PRIDE. To go from YAML to UDB, you must quote any unquoted strings. This process is automated with the Python conversion script [convertudb.py](../python/convertudb.py). This script also go from UDB to YAML by unquoting any strings that are typically unquoted.

### Conversion Script Location

The conversion script can be found [here](../python/convertudb.py) (`tools/python/convertudb.py`).

### Using the Conversion Script

*Note: Using this script requires a Python installation*

1. Download [convertudb.py](../python/convertudb.py) and place it in the same directory as the `.yaml` or `.udb` file you wish to convert.

2. Open your terminal and navigate to that directory:

   ```bash
   cd /path/to/file/directory
   ```

3. Run the conversion script. To go from YAML to UDB, use the command

   ```bash
   python convertudb.py filename.yaml
   ```

    To go from UDB to YAML, instead run

    ```bash
    python convertudb.py filename.udb
    ```

    Essentially, the `convertudb.py` script takes in either a `.yaml` or `.udb` file as its only argument. If it receives a `.yaml` or `.yml` file, it will convert to `.udb`. If it receives a `.udb` file, it will convert it to `.yaml`.

After running the script, a new file will be created in the same directory with the same filename but opposite file extension. As an example, if the input is `vsstatus.yaml` (or `vsstatus.yml`), the output will be `vsstatus.udb`.

This conversion script allows for two possible workflows for users. See our [user guide](udb-vscode/README.md) for more details.

Note that there's also a help option to print usage information:

```bash
python convertudb.py -h
```

or

```bash

python convertudb.py --help
```

### Modifying the Conversion Script

As UDB gets updated, the conversion script must also be updated to ensure expected behavior for end users.

Currently, the conversion scripts by keeping track of which fields contain string values in a number of different lists:

- `QUOTED_FIELDS` contains fields whose value is *always* a quoted string
  - e.g. `version: "1.0.0"`
- `STRING_FIELDS` contains fields whose value typically contains an unquoted string
  - e.g. `name: vcsr`
- `HAS_STRINGS` contains fields that aren't entirely strings, but may have strings inside of them
  - e.g. `release: { $ref: "releaseAddress" }`
- `YAML_ARRAY_STRING_FIELDS` contains fields whose values are YAML arrays of unquoted strings
- `YAML_ARRAY_HAS_STRINGS` contains fields that are YAML arrays with elements that may have strings in them.
  - e.g. `hints` may have an element that looks like
`- { $ref: "inst/Zihintntl/c.ntl.p1.yaml#" }`
- `YAML_ARRAY_ARRAY_STRINGS` are fields that are YAML arrays whose elements are themselves arrays of strings.
  - e.g. elements would like `- ["A", "B", "C"]`
- `YAML_LIST_STRING_FIELDS` are fields that are YAML arrays of strings, but without `-` prefixing every element
- `YAML_ARRAY_OR_STRING_FIELDS` are fields that can be either a YAML array of unquoted strings or just an unquoted string
- `ARRAY_STRING_FIELDS` are fields that are normal arrays of strings
  - e.g., `["F", "D", "V"]`
- `ARRAY_OR_STRING_FIELDS` are fields that can be either a string or an array
  - e.g., `affectedBy` could be `"F"` or `["F", "D", "V"]`
- `MAYBE_STRING` are for fields that *could* be an unquoted string. This mostly just happens for conditions.

Modifying the script mostly just involves adding a the relevant fields to the right list.

---

## Other Notes & Quirks

This is the extent of the current state of PRIDE. You'll note that the Xtext project also has some additional packages not mentioned in this documentation. Namely, `org.xtext.udb.ide`, `org.xtext.udb.web`, and `org.xtext.udb.ui`. These are packages we did not mess with, but could be used for things like a web editor or further customizing the IDE.
