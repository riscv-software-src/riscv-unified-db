package org.xtext.example.udb;

import org.eclipse.xtext.common.services.DefaultTerminalConverters;
import org.eclipse.xtext.conversion.IValueConverter;
import org.eclipse.xtext.conversion.ValueConverter;
import org.eclipse.xtext.conversion.ValueConverterException;
import org.eclipse.xtext.nodemodel.INode;

public class UDBValueConverterService extends DefaultTerminalConverters {
	
	/**
	 * INT converter for hex digits
	 */
	@ValueConverter(rule = "INT")
	public IValueConverter<Integer> INT() {
		return new IValueConverter<Integer>() {
			
			@Override
			public Integer toValue(String string, INode node) throws ValueConverterException {
				if (string == null) {
					return null;
				}
				try {
					// remove underscores
					String normalized = string.replace("_", "");
					
					if (normalized.startsWith("0x") || normalized.startsWith("0X")) {
						// parse as hex
						return Integer.parseUnsignedInt(normalized.substring(2), 16);
					} else {
						// parse as decimal
						return Integer.parseInt(normalized);
					}
				} catch (NumberFormatException e) {
					throw new ValueConverterException("Invalid integer literal: " + string, node, e);
				}
			}
			
			@Override
			public String toString(Integer value) {
				return value.toString();
			}
		};
	}
}
