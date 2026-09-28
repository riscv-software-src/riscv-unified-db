package org.xtext.example.udb.validation;

import org.eclipse.emf.common.util.EList;
import org.eclipse.emf.ecore.EObject;
import org.eclipse.xtext.validation.Check;
import org.xtext.example.udb.udb.UdbPackage;
import org.xtext.example.udb.treetop.TreetopParser;
import org.xtext.example.udb.treetop.ValidationError;

import org.xtext.example.udb.udb.Base;
import org.xtext.example.udb.udb.Url;
import org.xtext.example.udb.udb.Email;
import org.xtext.example.udb.udb.StringArray;

// Csr imports
import org.xtext.example.udb.udb.CsrModel;
import org.xtext.example.udb.udb.CsrName;
import org.xtext.example.udb.udb.CsrAddress;
import org.xtext.example.udb.udb.CsrAffectedByList;
import org.xtext.example.udb.udb.CsrAffectedBySingle;
import org.xtext.example.udb.udb.CsrAffectedByValue;
import org.xtext.example.udb.udb.CsrFieldAffectedBy;
import org.xtext.example.udb.udb.CsrVirtualAddress;
import org.xtext.example.udb.udb.CsrIndirectAddress;
import org.xtext.example.udb.udb.CsrIndirectSlot;
import org.xtext.example.udb.udb.CsrLength;
import org.xtext.example.udb.udb.CsrIntType;
import org.xtext.example.udb.udb.CsrFieldDef;
import org.xtext.example.udb.udb.CsrFieldAliasName;
import org.xtext.example.udb.udb.CsrSwRead;
import org.xtext.example.udb.udb.CsrFieldResetValueFunc;
import org.xtext.example.udb.udb.CsrFieldSWWriteFunc;
import org.xtext.example.udb.udb.CsrFieldLegalFunc;
import org.xtext.example.udb.udb.CsrFieldTypeFunc;

// Inst imports
import org.xtext.example.udb.udb.InstModel;
import org.xtext.example.udb.udb.InstName;
import org.xtext.example.udb.udb.InstHints;
import org.xtext.example.udb.udb.InstFormat;
import org.xtext.example.udb.udb.InstOldEncoding;
import org.xtext.example.udb.udb.InstEncoding;
import org.xtext.example.udb.udb.InstEncodingMatch;
import org.xtext.example.udb.udb.InstHintElement;
import org.xtext.example.udb.udb.InstRvPairEncoding;
import org.xtext.example.udb.udb.InstEncodingTwoKeyVar;
import org.xtext.example.udb.udb.InstEncodingSevenKeyVar;
import org.xtext.example.udb.udb.InstEncodingVariables;
import org.xtext.example.udb.udb.InstOperation;

// Extension imports
import org.xtext.example.udb.udb.ExtModel;
import org.xtext.example.udb.udb.ExtName;
import org.xtext.example.udb.udb.ExtVersionArrayElement;
import org.xtext.example.udb.udb.ExtVersionRatificationDate;

// Profile imports
import org.xtext.example.udb.udb.ProfModel;
import org.xtext.example.udb.udb.ProfInherits;
import org.xtext.example.udb.udb.ProfRelease;
import org.xtext.example.udb.udb.ProfExtInheritsString;
import org.xtext.example.udb.udb.ProfExtArrayElement;
import org.xtext.example.udb.udb.ProfExtVersionReqString;
import org.xtext.example.udb.udb.ProfExtRemoveString;

//Inst Opcode imports
import org.xtext.example.udb.udb.InstOpcodeModel;
import org.xtext.example.udb.udb.InstOpcodeData;
import org.xtext.example.udb.udb.InstOpcodeEntry;
import org.xtext.example.udb.udb.InstOpcodeInherits;

// Interrupt Code imports
import org.xtext.example.udb.udb.InterruptCodeModel;
import org.xtext.example.udb.udb.IntrptCodeName;

// Exception Code imports
import org.xtext.example.udb.udb.ExceptionCodeModel;

// Inst Var Type imports
import org.xtext.example.udb.udb.InstVarTypeModel;
import org.xtext.example.udb.udb.VarTypeEnum;

// Register imports
import org.xtext.example.udb.udb.ExtensionRequirement;
import org.xtext.example.udb.udb.RegisterModel;
import org.xtext.example.udb.udb.RegisterName;
import org.xtext.example.udb.udb.RegisterRole;
import org.xtext.example.udb.udb.RegisterRoles;
import org.xtext.example.udb.udb.Registers;
import org.xtext.example.udb.udb.RequiresEntry;
import org.xtext.example.udb.udb.RequiresNot;
import org.xtext.example.udb.udb.RegisterAbiMnemonics;
import org.xtext.example.udb.udb.RegisterClass;
import org.xtext.example.udb.udb.RegisterEntry;
import org.xtext.example.udb.udb.RegisterLength;
import org.xtext.example.udb.udb.RegisterLengthInt;
import org.xtext.example.udb.udb.RegisterLengthType;
import org.xtext.example.udb.udb.RegVersionRequirementString;
import org.xtext.example.udb.udb.RegisterArchRead;
import org.xtext.example.udb.udb.RegisterArchWrite;

// Manual imports
import org.xtext.example.udb.udb.ManualModel;

// Manual Version imports
import org.xtext.example.udb.udb.ManualVersionManual;
import org.xtext.example.udb.udb.ManualVersionModel;
import org.xtext.example.udb.udb.ManualVersionVersion;
import org.xtext.example.udb.udb.ExtensionElement;

// Profile Family imports
import org.xtext.example.udb.udb.ProfFamModel;

// Conditions imports
import org.xtext.example.udb.udb.ExtRequirement;
import org.xtext.example.udb.udb.ExtArrayList;
import org.xtext.example.udb.udb.ParamFieldsList;
import org.xtext.example.udb.udb.ParamArrayList;
import org.xtext.example.udb.udb.ParamOneOf;
import org.xtext.example.udb.udb.XLenCondition;

// Config imports
import org.xtext.example.udb.udb.ConfigModel;
//import org.xtext.example.udb.udb.ConfigParam;
import org.xtext.example.udb.udb.FullConfigurationType;
import org.xtext.example.udb.udb.ImplementedExtensionElement;
import org.xtext.example.udb.udb.PartialConfigurationType;
import org.xtext.example.udb.udb.UnconfigurationType;

// Non ISA imports
import org.xtext.example.udb.udb.NonIsaModel;
import org.xtext.example.udb.udb.NonIsaName;
import org.xtext.example.udb.udb.NonIsaRatificationDate;
import org.xtext.example.udb.udb.NonIsaVersion;
import org.xtext.example.udb.udb.Section;
/**
 * This class contains custom validation rules.
 *
 * See https://www.eclipse.org/Xtext/documentation/303_runtime_concepts.html#validation
 */
public class UdbValidator extends AbstractUdbValidator {

	// Regex's found throughout schemas (mostly in schema_defs.json)
	String rviVersionRegex = "^[0-9]+(\\.[0-9]+(\\.[0-9]+(-pre)?)?)?$";
	String csrFieldRegex = "^[a-z][a-z0-9_.]+\\.[A-Z0-9]+$";
    String csrFieldBitsRegex = "^[a-z][a-z0-9_.]+\\.[A-Z0-9]+\\[[0-9]+(:[0-9]+)?\\]$";
    String csrNameRegex = "^[a-z][a-z0-9_.]+$";
    String csrAffectedByRegex = "^(RV64)|([A-WY]|(Z[a-z]+)|(S[a-z]+))$";
    String extensionNameRegex = "^(([A-WY])|([SXZ][a-z0-9]+))$";
    String instNameRegex= "[a-z0-9.]+";
    String instHintsRegex = "^inst/.+\\.yaml#.*$";
    String instInheritTypeRegex="^.+\\.yaml#(/.*)?$";
    String instOpcodeInheritTypeRegex="inst_opcode/[^/]+\\.yaml#/data";
    String instChildOfRegex="common/inst_variable_types\\.yaml#/[a-zA-Z0-9_]+";
    String versionRequirementsRegex="^((>=)|(>)|(~>)|(<)|(<=)|(=))?\\s*[0-9]+(\\.[0-9]+(\\.[0-9]+(-[a-fA-F0-9]+)?)?)?$";
    String paramNameRegex="^[A-Z][A-Z_0-9]*$";
    String ENC_48 = "^[01-]{43}11111$";
    String ENC_32 = "^[01-]{30}11$";
    String ENC_16 = "^[01-]{14}((00)|(01)|(10))$";
    String legalIDLName="^[a-zA-Z_][a-zA-Z0-9_]*$";
    String registerFileNameRegex="^[A-Z]$";
    String registerNameRegex="^[A-Za-z][A-Za-z0-9_.-]*$";
    String registerAliasRegex="^[A-Za-z][A-Za-z0-9_.-]*$";
    String requirementStringRegex="^((>=)|(>)|(~>)|(<)|(<=)|(=))?\\s*[0-9]+(\\.[0-9]+(\\.[0-9]+(-[a-fA-F0-9]+)?)?)?$";
    String manualVersionManualRegex = "^manual/.*\\.yaml#$";
    String semanticVersionRegex = "^(0|[1-9]\\d*)\\.(0|[1-9]\\d*)\\.(0|[1-9]\\d*)(?:-((?:0|[1-9]\\d*|\\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\\.(?:0|[1-9]\\d*|\\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\\+([0-9a-zA-Z-]+(?:\\.[0-9a-zA-Z-]+)*))?$";
    String manualVersionExtensionVersion = "^[0-9]+(\\.[0-9]+(\\.[0-9]+(-pre)?)?)?$";
    String profInheritsRegex = "^profile/.*#$";
    String profReleaseRegex = "^profile_release.*#$";
    String profInheritsExtRegex = "^profile/.*#/extensions$";
    String nonISANameRegex = "^[A-Za-z][A-Za-z0-9_]*$";

    // Extra regex's for validation
    String urlRegex = "^https?:\\/\\/[^\\s/$.?#].[^\\s]*$";
    String refUrlRegex = "^.*/.*\\.yaml#.*$";
    String emailRegex = "^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$";
    String yearMonthDayRegex = "^\\d{4}-\\d{2}-\\d{2}$";
    String yearMonthRegex = "^\\d{4}-\\d{2}$";



    /*
     * CSR Validation -- rules found in csr_schema.json
     */

    // Ensure CSR schema matches csr_schema.json#
    @Check
    public void checkCsrSchema(CsrModel csr) {
		String schema = csr.getSchema().getSchema();
		if (!schema.equals("csr_schema.json#")) {
			error("Schema incompatible with kind", csr.getSchema(),
					UdbPackage.eINSTANCE.getSchema_Schema());
		}
    }

    // Validate CSR name matches required pattern
	@Check
	public void checkCsrName(CsrName name) {
	    String value = name.getName();
	    if (!value.matches(csrNameRegex)) {
	        error("Invalid csr name",
	              UdbPackage.eINSTANCE.getCsrName_Name());
	    }
	}

	// Address must be between 0 and 12 bits
	@Check
	public void checkCsrAddressVal(CsrAddress address) {
		int val = address.getAddress().getValue();
		if (val < 0 || val > 4096) {
			error("Address must be between 0 and 12 bits.",
					UdbPackage.eINSTANCE.getCsrAddress_Address());
		}
	}

	// Virtual address must be between 0 and 12 bits
	@Check
	public void checkCsrVirtualAddressVal(CsrVirtualAddress vaddress) {
		int val = vaddress.getVirtualAddress().getValue();

		if (val < 0 || val > 4096) {
			error("Virtual address must be between 0 and 12 bits.",
					UdbPackage.eINSTANCE.getCsrVirtualAddress_VirtualAddress());
		}
	}

	// Indirect address must be between 0 and 64 bits
	@Check
	public void checkCsrIndirectAddressVal(CsrIndirectAddress iaddress) {
		int val = iaddress.getIndirectAddress().getValue();

		if(val < 0 || val > (2^64)) {
			error("Indirect address must be between 0 and 64 bits.",
					UdbPackage.eINSTANCE.getCsrIndirectAddress_IndirectAddress());
		}
	}

	// Indirect_slot must be between 1 and 6
	@Check
	public void checkCsrIndirectSlotVal(CsrIndirectSlot indirectSlot) {
		int slot = indirectSlot.getIndirectSlot();

		if (slot < 1 || slot > 6) {
			error("Indirect slot value must be between 1 and 6.",
					UdbPackage.eINSTANCE.getCsrIndirectSlot_IndirectSlot());
		}
	}

	// Ensure indirect slot is present when indirect address is specified
	@Check
	public void checkCsrIndirectSlot(CsrModel csr) {
		CsrIndirectAddress iaddress = csr.getIndirectAddress();

		if (iaddress != null) {
			if (csr.getIndirectSlot() == null) {
				error("Indirect address requires an indirect slot.",
						UdbPackage.eINSTANCE.getCsrModel_IndirectSlot());
			}
		}

	}

	// Ensure virtual address is present when privilege mode is VS
	@Check
	public void checkCsrVirtualAddress(CsrModel csr) {
		String mode = csr.getPrivmode() != null ? csr.getPrivmode().getPrivMode() : null;

		if (mode.equals("VS")) {
			if (csr.getVirtualAddress() == null) {
				error("VS mode requires a virtual address.",
						UdbPackage.eINSTANCE.getCsrModel_Privmode());
			}
		}

	}

	@Check
	public void checkLengthValue(CsrLength length) {
		CsrIntType lengthInt = length.getLength().getIntType();

		// Containment reference is always instantiated
		if (length.getLength() == null) {
			error("length should not be null",
					UdbPackage.eINSTANCE.getCsrLength_Length());
		}

		// If length is an integer, value is either 32 or 64
		if (lengthInt != null) {
			int lengthVal = lengthInt.getIntVal();
			if (lengthVal != 32 && lengthVal != 64) {
				error("length if specified as integer, should be 32 or 64",
						UdbPackage.eINSTANCE.getCsrLength_Length());
			}
		}
	}

	@Check
	public void checkCsrFieldName(CsrFieldDef field) {
		String value = field.getName();
		if (!value.matches("^[a-zA-Z].*$")) {
			error("Invalid field name",
					UdbPackage.eINSTANCE.getCsrFieldDef_Name());
		}
	}

	// Validate CSR field alias matches CSR_FIELD or CSR_FIELD_BITS format
	@Check
	public void checkCsrFieldAlias(CsrFieldAliasName alias) {
		String value = alias.getName();

	    if (!value.matches(csrFieldRegex) &&
	        !value.matches(csrFieldBitsRegex)) {

	        error(
	            "Alias must match CSR_FIELD or CSR_FIELD_BITS format",
	            UdbPackage.eINSTANCE.getCsrFieldAliasName_Name());
	    }
	}

	// Validate CSR field affectedBy references valid extension names
	@Check
	public void checkCsrFieldAffectedBy(CsrFieldAffectedBy affectedBy) {
		CsrAffectedByValue value = affectedBy.getValue();

		if (value instanceof CsrAffectedBySingle) {
			CsrAffectedBySingle single = (CsrAffectedBySingle) value;
			ExtModel ref = single.getRef();

			if (ref != null) {
				ExtName extName = ref.getExtName();
				if (extName != null) {
					String name = extName.getName();
					if (!name.matches(csrAffectedByRegex)) {
						error("Extension name '" + name + "' does not follow valid format: must be RV64 or a single letter (A-Z except X) optionally followed by lowercase letters/numbers",
								UdbPackage.eINSTANCE.getCsrFieldAffectedBy_Value());
					}
				}
			}

		} else if (value instanceof CsrAffectedByList) {
			CsrAffectedByList list = (CsrAffectedByList) value;
			EList<ExtModel> refs = list.getRefs();

			for (ExtModel ref : refs) {
				if (ref != null) {
					ExtName extName = ref.getExtName();
					if (extName != null) {
						String name = extName.getName();
						if (!name.matches(csrAffectedByRegex)) {
							error("Extension name '" + name + "' does not follow valid format: must be RV64 or a single letter (A-Z except X) optionally followed by lowercase letters/numbers",
									UdbPackage.eINSTANCE.getCsrFieldAffectedBy_Value());
						}
					}
				}
			}
		}
	}



	/*
	 * Instruction Validation -- rules found in inst_schema.json
	 */
	@Check
	public void checkInstSchema(InstModel inst) {
		String schema = inst.getSchema().getSchema();
		if (!schema.equals("inst_schema.json#")) {
			error("Schema incompatible with kind", inst.getSchema(),
					UdbPackage.eINSTANCE.getSchema_Schema());
		}
	}

	// Validate instruction name matches required pattern
	@Check
	public void checkInstName(InstName name) {
	    String value = name.getName();
	    if (!value.matches(instNameRegex)) {
	        error("Invalid inst name", name, UdbPackage.eINSTANCE.getInstName_Name());
	    }
	}

	// Check access detail field is present when at least one mode
	// within access field is sometimes
	@Check
	public void checkInstAccessDetail(InstModel inst) {
		String accessdetail = inst.getAccessDetail() != null ? inst.getAccessDetail().getAccessDetail(): null;

		String m = inst.getAccess().getM() != null ? inst.getAccess().getM().getAccessLevel(): null;
		String s = inst.getAccess().getS() != null ? inst.getAccess().getS().getAccessLevel(): null;
		String u = inst.getAccess().getU() != null ? inst.getAccess().getU().getAccessLevel(): null;
		String vs = inst.getAccess().getVs() != null ? inst.getAccess().getVs().getAccessLevel(): null;
		String vu = inst.getAccess().getVu() != null ? inst.getAccess().getVu().getAccessLevel(): null;


		if (accessdetail == null || accessdetail.trim().isEmpty()) {
			if ("sometimes".equals(m)) {
				error("Must provide access_detail field when at least one access type is sometimes",
						inst.getAccess(),
						UdbPackage.eINSTANCE.getInstAccess_M());
			}
			if ("sometimes".equals(s)) {
				error("Must provide access_detail field when at least one access type is sometimes",
						inst.getAccess(),
						UdbPackage.eINSTANCE.getInstAccess_S());
			}
			if ("sometimes".equals(u)) {
				error("Must provide access_detail field when at least one access type is sometimes",
						inst.getAccess(),
						UdbPackage.eINSTANCE.getInstAccess_U());
			}
			if ("sometimes".equals(vs)) {
				error("Must provide access_detail field when at least one access type is sometimes",
						inst.getAccess(),
						UdbPackage.eINSTANCE.getInstAccess_Vs());
			}
			if ("sometimes".equals(vu)) {
				error("Must provide access_detail field when at least one access type is sometimes",
						inst.getAccess(),
						UdbPackage.eINSTANCE.getInstAccess_Vu());
			}

		}
	}

	// Validate instruction hints follow format $ref: inst/<path>.yaml#
	@Check
	public void checkInstHints(InstHints hints) {
		EList<InstHintElement> hintValue = hints != null ? hints.getHints(): null;

		for (InstHintElement hint : hintValue) {
			String hintString = hint.getHint();

			if (!(hintString.matches(instHintsRegex))) {
				error("hints must be of format $ref: inst/<path>.yaml# or $ref: inst/<path>.yaml#/...",
						hints,
						UdbPackage.eINSTANCE.getInstHints_Hints());
			}
		}
	}

	// Validate instruction inherits addresses match expected format
	@Check
	public void checkInstInherits(InstFormat format) {
	  if (format == null) return;

	  // 1. top-level inherits list
	  if (format.getInherits() != null && format.getInherits().getReference() != null) {
	    for (String address : format.getInherits().getReference()) {
	      if (address == null) continue; // or error if you want to require it
	      if (!address.matches(instInheritTypeRegex)) {
	        error(
	          "$inherits field must follow expected format: <path>.yaml# or <path>.yaml#/<fragment>.",
	          format,
	          UdbPackage.eINSTANCE.getInstFormat_Inherits()
	        );
	      }
	    }
	  }

	  // 2. opcode inherits
	  if (format.getOpcodes() == null || format.getOpcodes().getOpcode() == null) return;

	  for (InstOpcodeEntry entry : format.getOpcodes().getOpcode()) {
	    if (entry instanceof InstOpcodeInherits opcodeInherits) {
	      String address = opcodeInherits.getInheritsAddress();
	      if (address == null) continue;
	      if (!address.matches(instOpcodeInheritTypeRegex)) {
	        error(
	          "$inherits field within opcodes must follow string address format inst_opcode/<file>.yaml#/data",
	          opcodeInherits,
	          UdbPackage.eINSTANCE.getInstOpcodeInherits_InheritsAddress()
	        );
	      }
	    }
	  }
	}

	// Validate instruction encoding match patterns for 16, 32, and 48-bit encodings
	@Check
	public void checkInstEncoding(InstEncoding encoding) {

		if (encoding instanceof InstOldEncoding) {
			InstOldEncoding oldEncoding = (InstOldEncoding) encoding;

			InstEncodingMatch match = oldEncoding.getMatch();
			String pattern = match.getPattern();
			//error(match + " this is match", UdbPackage.Literals.INST_MODEL__ENCODING);

			// if match doesn't match any of these
			if (!(pattern.matches(ENC_48)) && !(pattern.matches(ENC_16)) && !(pattern.matches(ENC_32))) {
				error("Expected match to follow one of these patterns: 48-bit ([01-]{43}11111), 32-bit ([01-]{30}11), or  16-bit ([01-]{14}(00|01|10)).",
						match,
						UdbPackage.eINSTANCE.getInstEncodingMatch_Pattern());
			}
		}

		else if (encoding instanceof InstRvPairEncoding) {
			InstRvPairEncoding rvEncoding = (InstRvPairEncoding) encoding;

			InstEncodingMatch Rv32Match = rvEncoding.getRv32().getMatch();
			InstEncodingMatch Rv64Match = rvEncoding.getRv64().getMatch();
			String Rv32Pattern = Rv32Match.getPattern();
			String Rv64Pattern = Rv64Match.getPattern();

			// if match doesn't match any of these
			if (!(Rv32Pattern.matches(ENC_48)) && !(Rv32Pattern.matches(ENC_16)) && !(Rv32Pattern.matches(ENC_32))) {
				error("Expected match to follow one of these patterns: 48-bit ([01-]{43}11111), 32-bit ([01-]{30}11), or  16-bit ([01-]{14}(00|01|10)).",
						Rv32Match,
						UdbPackage.eINSTANCE.getInstEncodingMatch_Pattern());
			}

			if (!(Rv64Pattern.matches(ENC_48)) && !(Rv64Pattern.matches(ENC_16)) && !(Rv64Pattern.matches(ENC_32))) {
				error("Expected match to follow one of these patterns: 48-bit ([01-]{43}11111), 32-bit ([01-]{30}11), or  16-bit ([01-]{14}(00|01|10)).",
						Rv64Match,
						UdbPackage.eINSTANCE.getInstEncodingMatch_Pattern());
			}
		}

	}

	// Validate $inherits and $child_of fields in encoding variables
	@Check
	public void checkInstInheritsAndChildOf(InstEncoding encoding) {

		if (!(encoding instanceof InstOldEncoding)) {
			return;
		}

		InstOldEncoding old = (InstOldEncoding) encoding;
		InstEncodingVariables varsList = old.getVariables();

		if (varsList == null) {
			return;
		}

		for (EObject var: varsList.getVars()) {
			if (var instanceof InstEncodingTwoKeyVar) {
				InstEncodingTwoKeyVar twoKey = (InstEncodingTwoKeyVar) var;
				String inherits = twoKey.getInherits();

				if (inherits != null && !(inherits.matches(instChildOfRegex))) {
					error("Expected $inherits to follow common/inst_variable_types\\.yaml#/SOMETHING format",
							twoKey,
							UdbPackage.eINSTANCE.getInstEncodingTwoKeyVar_Inherits());
				}
			} else if (var instanceof InstEncodingSevenKeyVar) {
				InstEncodingSevenKeyVar sevenKey = (InstEncodingSevenKeyVar) var;
				String childOf = sevenKey.getChildOf();

				if (childOf != null && !(childOf.matches(instChildOfRegex))) {
					error("Expected $child_of to follow common/inst_variable_types\\.yaml#/SOMETHING format",
							sevenKey,
							UdbPackage.eINSTANCE.getInstEncodingSevenKeyVar_ChildOf());
				}
			}
		}
	}



	/*
	 * Extension Validation -- rules found in ext_schema.json
	 */

	// Ensure extension schema matches ext_schema.json#
    @Check
    public void checkExtSchema(ExtModel ext) {
		String schema = ext.getSchema().getSchema();
		if (!schema.equals("ext_schema.json#")) {
			error("Schema incompatible with kind", ext.getSchema(),
					UdbPackage.eINSTANCE.getSchema_Schema());
		}
    }

    // Validate extension name matches required pattern
	@Check
	public void checkExtName(ExtName name) {
	    String value = name.getName();
	    if (!value.matches(extensionNameRegex)) {
	        error("Invalid extension name",
	              UdbPackage.eINSTANCE.getExtName_Name());
	    }
	}

	// Validate extension version format and ratification date requirements
	@Check
	public void checkExtVersionArrayElement(ExtVersionArrayElement elem) {
		// Validate elements in the versions array

		// check that the string representation of the version is valid
    	String versionString = elem.getVersion();
    	if (!versionString.matches(rviVersionRegex)) {
			error("Invalid version",
					UdbPackage.eINSTANCE.getExtVersionArrayElement_Version());
		}

    	// if state is ratified, a ratification date must be given
    	String versionState = elem.getVersionState().getState();
		if (versionState.equals("ratified")) {
			if (elem.getRatificationDate() == null) {
				error("Ratified states require a ratification date.",
						UdbPackage.eINSTANCE.getExtVersionArrayElement_VersionState());
			}
		}
	}

    @Check
    public void checkExtVerDate(ExtVersionRatificationDate date) {
		String shortDate = date.getDate();
		if (!shortDate.matches(yearMonthRegex)) {
			error("Ratification Date must be year-month",
					UdbPackage.eINSTANCE.getExtVersionRatificationDate_Date());
		}
    }

	/*
	 * Profile Validation -- rules found in profile_schema.json
	 */
	@Check
	public void checkProfSchema(ProfModel prof) {
		String schema = prof.getSchema().getSchema();
		if (!schema.equals("profile_schema.json#")) {
			error("Schema incompatible with kind", prof.getSchema(),
					UdbPackage.eINSTANCE.getSchema_Schema());
		}
    }

	@Check
	public void checkProfInherits(ProfInherits inherits) {
		String inherit = inherits.getInherits();
		if (!inherit.matches(profInheritsRegex)) {
			error("Invalid path for inheritance",
					UdbPackage.eINSTANCE.getProfInherits_Inherits());
		}
	}

	@Check
	public void checkProfReleaseRef(ProfRelease release) {
		String ref = release.getReleaseAddress();
		if (!ref.matches(profReleaseRegex)) {
			error("Invalid release address",
					UdbPackage.eINSTANCE.getProfRelease_ReleaseAddress());
		}
	}

	@Check
	public void checkProfExtensionsInherits(ProfExtInheritsString inherits) {
		String inherit = inherits.getExtAddress();
		if (!inherit.matches(profInheritsExtRegex)) {
			error("Invalid path to inherited extension",
					UdbPackage.eINSTANCE.getProfExtInheritsString_ExtAddress());
		}
	}

	@Check
	public void checkProfExtensionsRemove(ProfExtRemoveString remove) {
		String name = remove.getExtName();
		if (!name.matches(extensionNameRegex)) {
			error("Invalid extension name",
					UdbPackage.eINSTANCE.getProfExtRemoveString_ExtName());
		}
	}

	@Check
	public void checkProfExtensionNames(ProfExtArrayElement extension) {
		String name = extension.getName();
		if (!name.matches("[A-Z][a-z0-9]*")) {
			error("Invalid extension name",
					UdbPackage.eINSTANCE.getProfExtArrayElement_Name());
		}
	}

	@Check
	public void checkProfVersionRequirements(ProfExtVersionReqString versionReq) {
		String req = versionReq.getVersionReq();
		if (!req.matches(requirementStringRegex)) {
			error("Invalid version requirement",
					UdbPackage.eINSTANCE.getProfExtVersionReqString_VersionReq());
		}
	}

	/*
	 * Interrupt Code Validation -- rules found in interrupt_code_schema.json
	 */
	@Check
    public void checkInterruptSchema(InterruptCodeModel intrptModel) {
		String schema = intrptModel.getSchema().getSchema();
		if (!schema.equals("interrupt_code_schema.json#")) {
			error("Schema incompatible with kind", intrptModel.getSchema(),
					UdbPackage.eINSTANCE.getSchema_Schema());
		}
    }

	// Validate interrupt code name is a legal IDL variable name
	@Check
	public void checkInterruptName(IntrptCodeName intrptName) {
		String value = intrptName.getName();
	    if (!value.matches(legalIDLName)) {
	        error("Invalid interrupt code name, must be legal IDL variable name",
	              UdbPackage.eINSTANCE.getIntrptCodeName_Name());
	    }

	}



	/*
     * Exception Code Validation -- rules found in exception_code_schema.json
     */
	@Check
    public void checkExceptionCodeSchema(ExceptionCodeModel model) {
		String schema = model.getSchema().getSchema();
		if (!schema.equals("exception_code_schema.json#")) {
			error("Schema incompatible with kind", model.getSchema(),
					UdbPackage.eINSTANCE.getSchema_Schema());
		}
    }



	/*
	 * Inst Opcode Validation -- rules found in inst_opcode_schema.json
	 */
	@Check
    public void checkInstOpcodeSchema(InstOpcodeModel instop) {
		String schema = instop.getSchema().getSchema();
		if (!schema.equals("inst_opcode_schema.json#")) {
			error("Schema incompatible with kind", instop.getSchema(),
					UdbPackage.eINSTANCE.getSchema_Schema());
		}
    }

	// Validate parent_of field follows ref url format
	@Check
	public void checkInstOpcodeParentOf(InstOpcodeData instopData) {
	    StringArray parentOfArray = instopData.getParentOf();
	    String parentOfString = instopData.getParentOfString();

	    // Check single string case
	    if (parentOfString != null && !parentOfString.matches(refUrlRegex)) {
	        error("Invalid ref url. Expected a .yaml file path with an anchor, like schemas/my-file.yaml#SectionName",
	              instopData,
	              UdbPackage.eINSTANCE.getInstOpcodeData_ParentOfString());
	    }

	    // Check array case
	    if (parentOfArray != null) {
	        for (String item : parentOfArray.getItem()) {
	            if (!item.matches(refUrlRegex)) {
	                error("Invalid ref url. Expected a .yaml file path with an anchor, like schemas/my-file.yaml#SectionName",
	                      instopData,
	                      UdbPackage.eINSTANCE.getInstOpcodeData_ParentOf());
	            }
	        }
	    }
	}



	/*
	 * InstVarType Validation -- rules found in inst_var_type_schema.json
	 */
	@Check
    public void checkInstVarTypeSchema(InstVarTypeModel model) {
		String schema = model.getSchema().getSchema();
		if (!schema.equals("inst_var_type_schema.json#")) {
			error("Schema incompatible with kind", model.getSchema(),
					UdbPackage.eINSTANCE.getSchema_Schema());
		}
    }

	// Validate register_file and access fields for register_reference type
	@Check
	public void checkRegisterReferenceFields(InstVarTypeModel model) {
		if (model.getInstVarTypeType() == null) return;

	    boolean isRegisterReference =
	        model.getInstVarTypeType().getType() == VarTypeEnum.REGISTER_REFERENCE;

	    if (isRegisterReference) {
	        // Fields REQUIRED for register_reference
	        if (model.getRegisterFile() == null)
	            error("register_file is required for register_reference type",
	                  UdbPackage.eINSTANCE.getInstVarTypeModel_RegisterFile());
	        if (model.getAccess() == null)
	            error("access is required for register_reference type",
	                  UdbPackage.eINSTANCE.getInstVarTypeModel_Access());
	    } else {
	        // Fields NOT ALLOWED when type is not register_reference
	        if (model.getRegisterFile() != null)
	            error("register_file is only valid when type is 'register_reference'",
	                  UdbPackage.eINSTANCE.getInstVarTypeModel_RegisterFile());
	        if (model.getAccess() != null)
	            error("access is only valid when type is 'register_reference'",
	                  UdbPackage.eINSTANCE.getInstVarTypeModel_Access());
	    }
	}

	/*
	 * Register File Validation -- rules found in register_schema.json
	 */

	/*
	 * Ensure register file schema matches register_file_schema.json#
	 * Spec: const: "register_file_schema.json#"
	 */
	@Check
	public void checkRegisterFileSchema(RegisterModel model) {
		String schema = model.getSchema().getSchema();
		if (!schema.equals("register_file_schema.json#")) {
			error("Schema incompatible with kind",
					UdbPackage.eINSTANCE.getSchema_Schema());
		}
	}

	/*
	 * Validate register file name matches pattern ^[A-Z]$
	 * Spec: pattern: "^[A-Z]$"
	 */
	@Check
	public void checkRegisterFileName(RegisterName name) {
		String value = name.getName();
	    if (!value.matches(registerFileNameRegex)) {
	        error("Invalid register file name'" + name + "': must be a single uppercase letter (A-Z)",
	              UdbPackage.eINSTANCE.getRegisterName_Name());
	    }
	}

	/*
	 * Validate register class is one of: general_purpose, floating_point, vector
	 * Spec: enum: ["general_purpose", "floating_point", "vector"]
	 */
	@Check
	public void checkRegisterClass(RegisterClass registerClass) {
		String registerClassValue = registerClass.getRegisterClass();

		if (registerClassValue == null) {
			error("Register class must be specified",
					UdbPackage.eINSTANCE.getRegisterClass_RegisterClass());
			return;
		}

		java.util.Set<String> ALLOWED_CLASSES = java.util.Set.of("general_purpose", "floating_point", "vector");

		if (!ALLOWED_CLASSES.contains(registerClassValue)) {
			error("Register class '" + registerClassValue + "' must be one of: general_purpose, floating_point, vector",
					UdbPackage.eINSTANCE.getRegisterClass_RegisterClass());
		}
	}

	/*
	 * Validate register length is valid bit length value
	 * Spec: $ref: schema_defs.json#/$defs/bit_length_value
	 */
	@Check
	public void checkRegisterLength(RegisterLength length) {
		RegisterLengthType bitLength = length.getRegisterLength();

		if (bitLength == null) {
			error("register_length must be specified",
					UdbPackage.eINSTANCE.getRegisterLength_RegisterLength());
			return;
		}

		// Check if it's an integer value
		if (bitLength.getIntVal() != null) {
			RegisterLengthInt intLength = bitLength.getIntVal();
			int val = intLength.getVal();

			if (val < 1) {
				error("register_length must be equal to or greater than 1",
						UdbPackage.eINSTANCE.getRegisterLength_RegisterLength());
			}
		}
	}

	/*
	 * Validate registers array has at least one entry
	 * Spec: minItems: 1
	 */
	@Check
	public void checkRegistersNotEmpty(Registers registers) {
		EList<RegisterEntry> entries = registers.getRegisters();

		if (entries == null || entries.size() == 0) {
			error("Registers array must have at least one entry",
					UdbPackage.eINSTANCE.getRegisters_Registers());
		}
	}

	/*
	 * Validate register name matches pattern ^[A-Za-z][A-Za-z0-9_.-]*$
	 * Spec: $ref: schema_defs.json#/$defs/register_name
	 */
	@Check
	public void checkRegisterName(RegisterEntry entry) {
		String name = entry.getName();

		if (name == null || name.isEmpty()) {
			error("Register name must not be empty",
					UdbPackage.eINSTANCE.getRegisterEntry_Name());
			return;
		}

		if (!name.matches(registerNameRegex)) {
			error("Register name '" + name + "' must start with a letter and contain only letters, numbers, underscores, dots, or hyphens",
					UdbPackage.eINSTANCE.getRegisterEntry_Name());
		}
	}

	/*
	 * Validate ABI mnemonics are unique
	 * Spec: uniqueItems: true
	 */
	@Check
	public void checkRegisterAbiMnemonicsUnique(RegisterAbiMnemonics mnemonics) {
		EList<String> mnemonicsList = mnemonics.getMnemonics();

		if (mnemonicsList == null || mnemonicsList.size() == 0) {
			return;
		}

		java.util.Set<String> seen = new java.util.HashSet<>();

		for (String mnemonic : mnemonicsList) {
			if (seen.contains(mnemonic)) {
				error("ABI mnemonic '" + mnemonic + "' is duplicated. Each mnemonic must be unique",
						UdbPackage.eINSTANCE.getRegisterAbiMnemonics_Mnemonics());
			}
			seen.add(mnemonic);
		}
	}

	/*
	 * Validate ABI mnemonic matches pattern ^[A-Za-z][A-Za-z0-9_.-]*$
	 * Spec: $ref: schema_defs.json#/$defs/register_alias
	 */
	@Check
	public void checkAbiMnemonicFormat(RegisterAbiMnemonics mnemonics) {
		EList<String> mnemonicsList = mnemonics.getMnemonics();

		if (mnemonicsList == null || mnemonicsList.size() == 0) {
			return;
		}

		for (String mnemonic : mnemonicsList) {
			if (mnemonic == null || mnemonic.isEmpty()) {
				error("ABI mnemonic must not be empty",
						UdbPackage.eINSTANCE.getRegisterAbiMnemonics_Mnemonics());
				continue;
			}

			if (!mnemonic.matches(registerAliasRegex)) {
				error("ABI mnemonic '" + mnemonic + "' must start with a letter and contain only letters, numbers, underscores, dots, or hyphens",
						UdbPackage.eINSTANCE.getRegisterAbiMnemonics_Mnemonics());
			}
		}
	}

	/*
	 * Validate register roles are unique
	 * Spec: uniqueItems: true
	 */
	@Check
	public void checkRegisterRolesUnique(RegisterRoles roles) {
		EList<RegisterRole> rolesList = roles.getRoles();

		if (rolesList == null || rolesList.size() == 0) {
			return;
		}

		java.util.Set<RegisterRole> seen = new java.util.HashSet<>();

		for (RegisterRole role : rolesList) {
			if (seen.contains(role)) {
				error("Register role '" + role + "' is duplicated. Each role must be unique",
						UdbPackage.eINSTANCE.getRegisterAbiMnemonics_Mnemonics());
			}
			seen.add(role);
		}
	}

	/*
	 * Validate extension name regex in requires entry
	 * Spec: extension name
	 */
	@Check
	public void checkRequiresEntry(RequiresEntry entry) {
		try {
			if (entry instanceof ExtensionRequirement) {
				ExtensionRequirement extReq = (ExtensionRequirement) entry;
				String name = extReq.getName();

				if (name == null) {
					error("Extension name is required", extReq,
							UdbPackage.eINSTANCE.getExtensionRequirement_Name());
					return;
				}

				if (name.isEmpty()) {
					error("Extension name cannot be empty", extReq,
							UdbPackage.eINSTANCE.getExtensionRequirement_Name());
					return;
				}

				if (!name.matches(extensionNameRegex)) {
					error("Extension name '" + name + "' must be a single letter (A-W or Y) OR a letter (S, X, or Z) followed by lowercase letters/numbers", extReq,
							UdbPackage.eINSTANCE.getExtensionRequirement_Name());
				}
			}
		} catch (Exception e) {
			return;
		}
	}


	/*
	 * Validate extension name in register requires not field follows pattern ^(([A-WY])|([SXZ][a-z0-9]+))$
	 * Spec: $ref: schema_defs.json#/$defs/extension_name
	 */
	@Check
	public void checkSimpleExtensionNameFormat(RequiresNot extReq) {
		try {
			if (extReq == null) {
				return;
			}
			String name = extReq.getName();

			if (name == null) {
				error("Extension name is required",
						UdbPackage.eINSTANCE.getRequiresNot_Name());
				return;
			}

			if (name.isEmpty()) {
				error("Extension name cannot be empty",
						UdbPackage.eINSTANCE.getRequiresNot_Name());
				return;
			}

			if (!name.matches(extensionNameRegex)) {
				error("Extension name '" + name + "' must be a single letter (A-W or Y) OR a letter (S, X, or Z) followed by lowercase letters/numbers",
						UdbPackage.eINSTANCE.getRequiresNot_Name());
			}
		} catch (Exception e) {
			// Silently ignore - malformed objects from optional INDENT/DEDENT
			return;
		}
	}



	/*
	 * Validate version requirement format matches pattern
	 * Spec: pattern: "^((>=)|(>)|(~>)|(<)|(<=)|(=))?\s*[0-9]+(\.[0-9]+(\.[0-9]+(-[a-fA-F0-9]+)?)?)?$"
	 */
	@Check
	public void checkVersionRequirementFormat(RegVersionRequirementString versionReq) {
		String version = versionReq.getVersion();

		if (version == null || version.isEmpty()) {
			error("Version requirement must not be empty",
					UdbPackage.eINSTANCE.getRegVersionRequirementString_Version());
			return;
		}


		if (!version.matches(requirementStringRegex)) {
			error("Version requirement '" + version + "' must match format: [operator] major[.minor[.patch[-prerelease]]]",
					UdbPackage.eINSTANCE.getRegVersionRequirementString_Version());
		}
	}

	/*
	 * Manual Validation -- rules found in manual_schema.json
	 */
	@Check
    public void checkManualSchema(ManualModel model) {
		String schema = model.getSchema().getSchema();
		if (!schema.equals("manual_schema.json#")) {
			error("Schema incompatible with kind", UdbPackage.eINSTANCE.getSchema_Schema());
		}
    }

    /*
     * Manual Version Validation -- rules found in manual_version_schema.json
     */
	@Check
	public void checkManualVersionSchema(ManualVersionModel model) {
		String schema = model.getSchema().getSchema();
		if (!schema.equals("manual_version_schema.json#")) {
			error("Schema incompatible with kind", model.getSchema(),
					UdbPackage.eINSTANCE.getSchema_Schema());
		}
	}

	@Check
	public void checkManualVersionManualString(ManualVersionManual manual) {
	    String value = manual.getRef();
	    if (!value.matches(manualVersionManualRegex)) {
	        error("Manual ref format must follow 'manual/[name].yaml#' format", manual,
	        		UdbPackage.eINSTANCE.getManualVersionManual_Ref());
	    }
	}

	@Check
	public void checkManualVersionVersionString(ManualVersionVersion version) {
	    String value = version.getVersion();
	    if (!value.matches(semanticVersionRegex)) {
	        error("Version must follow semantic versioning format (e.g. 1.2.3, 1.0.0-alpha.1, 2.3.4+build.42)", version, UdbPackage.eINSTANCE.getManualVersionVersion_Version());
	    }
	}

	@Check
	public void checkManualVersionExtensionVersion(ExtensionElement element) {
	    String value = element.getVersion();
	    if (!value.matches(manualVersionExtensionVersion)) {
	        error("Version must be a numeric version string (e.g. 1, 1.2, 1.2.3, or 1.2.3-pre)", element, UdbPackage.eINSTANCE.getExtensionElement_Version());
	    }
	}



	/*
	 * Profile Family Validation -- rules found in profile_family_schema.json
	 */
    @Check
    public void checkProfileFamilySchema(ProfFamModel model) {
		String schema = model.getSchema().getSchema();
		if (!schema.equals("profile_family_schema.json#")) {
			error("Schema incompatible with kind", model.getSchema(),
					UdbPackage.eINSTANCE.getSchema_Schema());
		}
    }



	/*
	 * Conditions Validation
	 */
	@Check
	public void checkExtReqName(ExtRequirement extReq) {
		String extName = extReq.getName();
		if (!extName.matches(extensionNameRegex)) {
			error("Invalid extension name.",
					UdbPackage.eINSTANCE.getExtRequirement_Name());
		}
	}

	@Check
	public void checkExtArraySize(ExtArrayList array) {
		int arraySize = array.getExtArray().size();
		if (arraySize < 2) {
			error("Minimum of two list items required.",
					UdbPackage.eINSTANCE.getExtArrayList_ExtArray());
		}
	}

	@Check
	public void checkExtVersion(ExtRequirement requirement) {
		String version = requirement.getVersion().getVerReqs().getVersionReq();
		if (!(version.matches(versionRequirementsRegex))){
			error("Invalid version format.",
					UdbPackage.eINSTANCE.getExtRequirement_Version());
		}
	}

	@Check
	public void checkParamName(ParamFieldsList name) {
		String paramName = name.getName();
		if (!paramName.matches(paramNameRegex)) {
			error("Invalid parameter name.",
					UdbPackage.eINSTANCE.getParamFieldsList_Name());
		}
	}

	@Check
	public void checkParamFieldsSize(ParamFieldsList fields) {
		int fieldsSize = fields.getParamFieldsList().size();
		if (!(fieldsSize > 0 && fieldsSize < 3)) {
			error("Must include 2-3 properties.",
					UdbPackage.eINSTANCE.getParamFieldsList_ParamFieldsList());
		}
	}

	@Check
	public void checkParamOneOfSize(ParamOneOf oneOf) {
		int oneOfSize = oneOf.getOneOf().size();
		if (oneOfSize < 2) {
			error("Minimum of two list items required.",
					UdbPackage.eINSTANCE.getParamOneOf_OneOf());
		}
	}

	@Check
	public void checkParamArraySize(ParamArrayList array) {
		int arraySize = array.getParamArray().size();
		if (arraySize < 2) {
			error("Minimum of two list items required.",
					UdbPackage.eINSTANCE.getParamArrayList_ParamArray());
		}
	}

	@Check
	public void checkXLenValue(XLenCondition xlen) {
		int xlenValue = xlen.getXlen();
		if (xlenValue != 32 && xlenValue != 64) {
			error("xlen must be 32 or 64.",
					UdbPackage.eINSTANCE.getXLenCondition_Xlen());
		}
	}



    /*
	 * Config Validation -- rules found in config_schema.json
	 */
    @Check
    public void checkConfigSchema(ConfigModel model) {
		String schema = model.getSchema().getSchema();
		if (!schema.equals("config_schema.json#")) {
			error("Schema incompatible with kind", model.getSchema(),
					UdbPackage.eINSTANCE.getSchema_Schema());
		}
    }

    @Check
	public void checkFullConfigurationType(FullConfigurationType config) {
		String type = config.getType();
		if (!type.equals("fully_configured")) {
			error("Type must be 'fully_configured' for Full Configuration",
					config,
					UdbPackage.eINSTANCE.getFullConfiguration_Type());
		}
	}

    @Check
   	public void checkFullConfigurationType(PartialConfigurationType config) {
   		String type = config.getType();
   		if (!type.equals("partially_configured")) {
   			error("Type must be 'partially_configured' for Partial Configuration",
   					config,
   					UdbPackage.eINSTANCE.getPartialConfiguration_Type());
   		}
   	}

    @Check
   	public void checkFullConfigurationType(UnconfigurationType config) {
   		String type = config.getType();
   		if (!type.equals("unconfigured")) {
   			error("Type must be 'unconfigured' for Unconfiguration",
   					config,
   					UdbPackage.eINSTANCE.getUnconfiguration_Type());
   		}
   	}

	@Check
	public void checkImplementedExtensionElement(ImplementedExtensionElement element) {
		if (element == null) return;

		String name = element.getName();
		String version = element.getVersion();

		if (name == null || name.trim().isEmpty()) {
			error("Extension name is required",
					element,
					UdbPackage.eINSTANCE.getImplementedExtensionElement_Name());
		}

		if (version == null || version.trim().isEmpty()) {
			error("Extension version is required",
					element,
					UdbPackage.eINSTANCE.getImplementedExtensionElement_Version());
		}

		// Validate name format
		if (name != null && !name.matches(extensionNameRegex)) {
			error("Invalid extension name '" + name + "': must be a single letter (A-W or Y) " +
					"OR a letter (S, X, or Z) followed by lowercase letters/numbers",
					element,
					UdbPackage.eINSTANCE.getImplementedExtensionElement_Name());
		}

		// Validate version format
		if (version != null && !version.matches(rviVersionRegex)) {
			error("Invalid version '" + version + "': must match pattern [0-9]+(\\.[0-9]+(\\.[0-9]+(-pre)?)?)?",
					element,
					UdbPackage.eINSTANCE.getImplementedExtensionElement_Version());
		}
	}



    /*
	 * Non ISA Validation -- rules found in config_schema.json
	 */
	@Check
	public void checkNonISASchema(NonIsaModel model) {
		String schema = model.getSchema().getSchema();
		if (!schema.equals("non_isa_schema.json#")) {
			error("Schema incompatible with kind", model.getSchema(), UdbPackage.eINSTANCE.getSchema_Schema());
		}
	}

	@Check
	public void checkNonISAName(NonIsaName nonisaname) {
		String name = nonisaname.getName();
		if (!name.matches(nonISANameRegex)) {
			error("Invalid Non-ISA name",
					UdbPackage.eINSTANCE.getNonIsaName_Name());
		}
	}

	@Check
	public void checkNonISAVersion(NonIsaVersion isaVer) {
		String name = isaVer.getVersion();
		if (!name.matches(semanticVersionRegex)) {
			error("Invalid Non-ISA version",
					UdbPackage.eINSTANCE.getNonIsaVersion_Version());
		}
	}

	@Check
	public void checkSection(Section section) {
		if (section == null) return;

		// Check required fields
		String title = section.getTitle();
		if (title == null || title.trim().isEmpty()) {
			error("Section title is required",
					section,
					UdbPackage.eINSTANCE.getSection_Title());
		}

		String content = section.getContent().getValue();
		if (content == null || content.trim().isEmpty()) {
			error("Section content is required",
					section,
					UdbPackage.eINSTANCE.getSection_Content());
		}

		// Check optional level field
		int level = section.getLevel();
		if (level != 0) { // 0 is default/unset
			if (level < 1 || level > 6) {
				error("Section level must be between 1 and 6 (inclusive); got " + level,
						section,
						UdbPackage.eINSTANCE.getSection_Level());
			}
		}
	}

    @Check
    public void checkNonIsaDate(NonIsaRatificationDate date) {
		String longDate = date.getDate();
		if (!longDate.matches(yearMonthDayRegex)) {
			error("Ratification Date must be year-month-day",
					UdbPackage.eINSTANCE.getNonIsaRatificationDate_Date());
		}
    }



	/*
	 *  Validate general fields (e.g. url, email, etc.)
	 */

	// Check that URLs follow the URI format
	@Check
	public void checkUrlFormat(Url url) {
		String urlString = url.getUrl();
		if (!urlString.matches(urlRegex)) {
			error("URL not in URI format", UdbPackage.eINSTANCE.getUrl_Url());
		}
	}

	// Check that emails follow email format
	@Check
	public void checkEmailFormat(Email email) {
		String emailString = email.getEmail();
		if (!emailString.matches(emailRegex)) {
			error("Email not in formatted correctly", UdbPackage.eINSTANCE.getEmail_Email());
		}
	}

	// Ensure base value is either 32 or 64
	@Check
	public void checkBase(Base base) {
		int baseNum = base.getBase();

		if (baseNum != 64 && baseNum != 32) {
			error("Base must be 32 for RV32I or 64 for RV64I",
					UdbPackage.eINSTANCE.getBase_Base());
		}
	}


	/*
	 * Pass off IDL to the treetop parser
	 */
	private final TreetopParser treetopParser = new TreetopParser();

	/**
     * Helper function for passing IDL snippets into treetop
     *
     * @param content   IDL source fragment
     * @param root		Rule name to use as the root (e.g. "function_call"),
     *                  or {@code null} for the grammar's default root.
     */
	public String checkIdl(String content, String root) {
	    // Strip surrounding quotes that Xtext adds to STRING terminals
	    if (content != null && content.startsWith("\"") && content.endsWith("\"")) {
	    	content = content.strip();
	    	content = content.substring(1, content.length() - 1);
	    }

	    ValidationError error = treetopParser.parse(content, root);
	    if (error != null) {
	        return error.reason;
	    }

	    return null;
	}


	// Csr IDL checks
	@Check
	public void checkCsrSwRead(CsrSwRead swRead) {
		String idl = swRead.getSwRead().getIdl();
		String idlError = checkIdl(idl, "function_body");

		if (idlError != null) {
			error(idlError, UdbPackage.eINSTANCE.getCsrSwRead_SwRead());
		}
	}

	@Check
	public void checkCsrFieldResetValueFunc(CsrFieldResetValueFunc resetVal) {
		String idl = resetVal.getResetValueFunc().getIdl();
		String idlError = checkIdl(idl, "function_body");

		if (idlError != null) {
			error(idlError,
					UdbPackage.eINSTANCE.getCsrFieldResetValueFunc_ResetValueFunc());
		}
	}

	@Check
	public void checkCsrFieldSWWriteFunc(CsrFieldSWWriteFunc swWrite) {
		String idl = swWrite.getSwWriteFunc().getIdl();
		String idlError = checkIdl(idl, "function_body");

		if (idlError != null) {
			error(idlError,
					UdbPackage.eINSTANCE.getCsrFieldSWWriteFunc_SwWriteFunc());
		}
	}

	@Check
	public void checkCsrFieldLegalFunc(CsrFieldLegalFunc legal) {
		String idl = legal.getLegalFunc().getIdl();
		String idlError = checkIdl(idl, "function_body");

		if (idlError != null) {
			error(idlError,
					UdbPackage.eINSTANCE.getCsrFieldLegalFunc_LegalFunc());
		}
	}

	@Check
	public void checkCsrFieldTypeFunc(CsrFieldTypeFunc type) {
		String idl = type.getIdl().getIdl();
		String idlError = checkIdl(idl, "function_body");

		if (idlError != null) {
			error(idlError,
					UdbPackage.eINSTANCE.getCsrFieldTypeFunc_Idl());
		}
	}


	// Instruction IDL checks
	@Check
	public void checkInstOperation(InstOperation op) {
		String idl = op.getOperation().getIdl();
		String idlError = checkIdl(idl, "function_body");

		if (idlError != null) {
			error(idlError,
					UdbPackage.eINSTANCE.getInstOperation_Operation());
		}
	}

	// Register file IDL checks
	@Check
	public void checkRegisterArchRead(RegisterArchRead arch) {
		String idl = arch.getArchRead().getIdl();

		// TODO: check that this is the right root node
		String idlError = checkIdl(idl, "function_body");

		if (idlError != null) {
			error(idlError,
					UdbPackage.eINSTANCE.getRegisterArchRead_ArchRead());
		}
	}

	@Check
	public void checkRegisterArchWrite(RegisterArchWrite arch) {
		String idl = arch.getArchWrite().getIdl();

		// TODO: check that this is the right root node
		String idlError = checkIdl(idl, "function_body");

		if (idlError != null) {
			error(idlError,
					UdbPackage.eINSTANCE.getRegisterArchWrite_ArchWrite());
		}
	}
}
