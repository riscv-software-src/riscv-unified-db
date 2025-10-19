package org.xtext.udb;

import org.eclipse.xtext.common.services.DefaultTerminalConverters;
import org.eclipse.xtext.conversion.IValueConverter;
import org.eclipse.xtext.conversion.ValueConverter;
import org.eclipse.xtext.conversion.ValueConverterException;
import org.eclipse.xtext.nodemodel.INode;

public class UDBValueConverter extends DefaultTerminalConverters {
	
	/**
	 * INT converter for hex digits
	 */
	@ValueConverter(rule = "HEX_VALUE")
	public IValueConverter<Integer> HEX_VALUE() {
		return new HexValueConverter();
	}
	
	public static class HexValueConverter implements IValueConverter<Integer> {

		@Override
		public Integer toValue(String string, INode node) throws ValueConverterException {
			try {
				// remove underscores
				String normalized = string.replace("_", "");
				return Integer.parseUnsignedInt(normalized.substring(2), 16);
				
			} catch (NumberFormatException e) {
				throw new ValueConverterException("Invalid integer literal: " + string, node, e);
			}
		}

		@Override
		public String toString(Integer value) throws ValueConverterException {
			return "0x" + Integer.toHexString(value);
		}
	}
	
}