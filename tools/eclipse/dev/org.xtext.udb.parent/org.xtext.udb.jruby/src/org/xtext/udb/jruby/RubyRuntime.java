package org.xtext.udb.jruby;

import org.jruby.embed.ScriptingContainer;
import org.jruby.embed.LocalContextScope;
import org.jruby.embed.LocalVariableBehavior;
import org.osgi.framework.Bundle;
import org.osgi.framework.FrameworkUtil;
import org.eclipse.core.runtime.FileLocator;
import java.io.File;
import java.io.StringWriter;
import java.io.IOException;
import java.net.URISyntaxException;
import java.net.URL;

public final class RubyRuntime {
    private static final ScriptingContainer ruby = new ScriptingContainer(
		LocalContextScope.SINGLETON,
	    LocalVariableBehavior.PERSISTENT
    );

    static {
    	try {
    		// resolve idlc paths -- copied into this package with Maven
    		File root = resolveRoot();
            File idlcDir   = new File(root, "idlc").getCanonicalFile();
            String idlcLib  = new File(idlcDir, "lib").getCanonicalPath();
            String gemfile  = new File(idlcDir, "Gemfile").getCanonicalPath();
            String vendorDir = new File(root, "vendor/bundle").getCanonicalPath();

            // Capture JRuby stdout/stderr so it surfaces in the Eclipse log
            StringWriter out = new StringWriter();
            StringWriter err = new StringWriter();
            ruby.setOutput(out);
            ruby.setError(err);

            // Build and run a single consolidated scriptlet
            String scriptlet = String.format("""
                # Point Bundler at the Gemfile Maven copied into the package
                ENV['BUNDLE_GEMFILE']             = '%s'
                ENV['BUNDLE_PATH']                = '%s'
                ENV['BUNDLE_WITHOUT']             = 'development'
                ENV['BUNDLE_DISABLE_SHARED_GEMS'] = '1'
                ENV['JARS_NO_REQUIRE']            = 'true'
                ENV['JARS_SKIP']                  = 'true'

                # Activate pre-vendored gems
			    require 'bundler'
			    Bundler.reset!
			    Bundler.setup(:default)
			    Bundler.require(:default)

                # Prepend idlc's own lib/ so require 'idlc' resolves correctly
                $LOAD_PATH.unshift('%s') unless $LOAD_PATH.include?('%s')
                require 'idlc'
                """,
                escape(gemfile),
                escape(vendorDir),
                escape(idlcLib),
                escape(idlcLib)
            );

            ruby.runScriptlet(scriptlet);

            System.out.println("[RubyRuntime] JRuby output:\n" + out);
            if (!err.toString().isEmpty()) {
                System.err.println("[RubyRuntime] JRuby errors:\n" + err);
            }

    	} catch (IOException | URISyntaxException e) {
    		throw new RuntimeException("Failed to resolve gems path", e);
    	}
    }


    /**
     * Resolves the bundle/project root directory in both OSGi and standalone
     * environments (e.g. JUnit).
     */
    private static File resolveRoot() throws IOException, URISyntaxException {
        Bundle bundle = FrameworkUtil.getBundle(RubyRuntime.class);

        if (bundle != null) {
            // OSGi path
            return new File(FileLocator.toFileURL(bundle.getEntry("/")).getPath())
                    .getCanonicalFile();
        }

        // Standalone / JUnit path
        URL classUrl = RubyRuntime.class.getProtectionDomain()
                                        .getCodeSource()
                                        .getLocation();
        File dir = new File(classUrl.toURI()).getCanonicalFile();

        // Walk upward — handles both target/classes and arbitrary output dirs
        File candidate = dir;
        while (candidate != null) {
            if (new File(candidate, "idlc").isDirectory()) {
                return candidate;
            }
            candidate = candidate.getParentFile();
        }

        throw new IOException(
            "Could not locate project root (directory containing 'idlc/') " +
            "starting from: " + dir
        );
    }

    public static ScriptingContainer get() {
        return ruby;
    }

    private static String escape(String path) {
        return path.replace("\\", "\\\\").replace("'", "\\'");
    }
}
