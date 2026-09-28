package org.xtext.example.udb.treetop;

import org.jruby.embed.ScriptingContainer;
import org.xtext.udb.jruby.RubyRuntime;

public class TreetopParser {

    private final ScriptingContainer ruby = RubyRuntime.get();

    public TreetopParser() {
    	ruby.runScriptlet("$idl_parser = IdlParser.new");

    	// Verify it was actually created
        Object check = ruby.runScriptlet("$idl_parser");
        if (check == null) {
            throw new RuntimeException(
                "[TreetopParser] IdlParser.new returned nil"
            );
        }
    }

    /**
     * Parse {@code input} starting at an optional Treetop rule.
     *
     * @param input     IDL source fragment
     * @param startRule Rule name to use as the root (e.g. "function_call"),
     *                  or {@code null} for the grammar's default root.
     */
    public ValidationError parse(String input, String startRule) {
        // Use ruby.put() to pass Java strings safely — avoids any quoting
        // issues if the IDL input itself contains single/double quotes.
        ruby.put("idl_input", input);

        Object result;
        if (startRule != null && !startRule.isEmpty()) {
        	result = ruby.runScriptlet(
                "$idl_parser.parse(idl_input, root: :" + startRule + ")"
            );
        } else {
        	result = ruby.runScriptlet(
                "$idl_parser.parse(idl_input)"
            );
        }

        if (result == null) {
            String reason = (String) ruby.runScriptlet("$idl_parser.failure_reason");
            int    line   = ((Long)  ruby.runScriptlet("$idl_parser.failure_line"  )).intValue();
            int    column = ((Long)  ruby.runScriptlet("$idl_parser.failure_column")).intValue();
            return new ValidationError(reason, line, column);
        }
        return null;
    }

    /** Convenience overload using the grammar's default root rule. */
    public ValidationError parse(String input) {
        return parse(input, null);
    }
}
