package org.xtext.example.udb.naming;
import org.eclipse.xtext.naming.DefaultDeclarativeQualifiedNameProvider;
import org.eclipse.xtext.naming.QualifiedName;
import org.eclipse.emf.ecore.EObject;
import org.xtext.example.udb.udb.CsrName;
import org.xtext.example.udb.udb.ECName;
import org.xtext.example.udb.udb.ExtModel;
import org.xtext.example.udb.udb.InstName;
import org.xtext.example.udb.udb.InstOpcodeName;
import org.xtext.example.udb.udb.InstVarTypeName;
import org.xtext.example.udb.udb.IntrptCodeName;
import org.xtext.example.udb.udb.ManualName;
import org.xtext.example.udb.udb.ManualVersionName;
import org.xtext.example.udb.udb.PFName;
import org.xtext.example.udb.udb.ExtName;
import org.xtext.example.udb.udb.RegisterName;

public class UdbQualifiedNameProvider extends DefaultDeclarativeQualifiedNameProvider {
	public QualifiedName qualifiedName(CsrName csrName) {
		if (csrName != null && csrName.getName() != null) {
			return QualifiedName.create(csrName.getName());
		}
		return null;
	}

	public QualifiedName qualifiedName(InstName instName) {
		if (instName != null && instName.getName() != null) {
			return QualifiedName.create(instName.getName());
		}
		return null;
	}

	public QualifiedName qualifiedName(ExtModel extModel) {
		if (extModel != null && extModel.getExtName() != null) {
			return QualifiedName.create(extModel.getExtName().getName());
		}
		return null;
	}

	public QualifiedName qualifiedName(ExtName extName) {
		if (extName != null && extName.getName() != null) {
			return QualifiedName.create(extName.getName());
		}
		return null;
	}

	public QualifiedName qualifiedName(IntrptCodeName intrptcodeName) {
		if (intrptcodeName != null && intrptcodeName.getName() != null) {
			return QualifiedName.create(intrptcodeName.getName());
		}
		return null;
	}
	
	public QualifiedName qualifiedName(ECName ecName) {
		if (ecName != null && ecName.getName() != null) {
			return QualifiedName.create(ecName.getName());
		}
		return null;
	}

	public QualifiedName qualifiedName(InstOpcodeName instopcodeName) {
		if (instopcodeName != null && instopcodeName.getName() != null) {
			return QualifiedName.create(instopcodeName.getName());
		}
		return null;
	}

	public QualifiedName qualifiedName(InstVarTypeName instvartypeName) {
		if (instvartypeName != null && instvartypeName.getName() != null) {
			return QualifiedName.create(instvartypeName.getName());
		}
		return null;
	}

	public QualifiedName qualifiedName(RegisterName regName) {
		if (regName != null && regName.getName() != null) {
			return QualifiedName.create(regName.getName());
		}
		return null;
	}

	public QualifiedName qualifiedName(ManualName manualName) {
		if (manualName != null && manualName.getName() != null) {
			return QualifiedName.create(manualName.getName());
		}
		return null;
	}

	public QualifiedName qualifiedName(ManualVersionName manualverName) {
		if (manualverName != null && manualverName.getName() != null) {
			return QualifiedName.create(manualverName.getName());
		}
		return null;
	}

	public QualifiedName qualifiedName(PFName pfName) {
		if (pfName != null && pfName.getName() != null) {
			return QualifiedName.create(pfName.getName());
		}
		return null;
	}
}
