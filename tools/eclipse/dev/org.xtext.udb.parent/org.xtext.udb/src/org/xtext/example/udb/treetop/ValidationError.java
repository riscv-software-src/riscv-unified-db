package org.xtext.example.udb.treetop;

public class ValidationError {
    public final String reason;
    public final int line;
    public final int column;

    public ValidationError(String reason, int line, int column) {
        this.reason = reason;
        this.line = line;
        this.column = column;
    }
}
