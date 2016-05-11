/******************************************************************************
 * Copyright (c) 2009-2016, Barthelemy Dagenais and individual contributors.
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 * - Redistributions of source code must retain the above copyright notice,
 * this list of conditions and the following disclaimer.
 *
 * - Redistributions in binary form must reproduce the above copyright notice,
 * this list of conditions and the following disclaimer in the documentation
 * and/or other materials provided with the distribution.
 *
 * - The name of the author may not be used to endorse or promote products
 * derived from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 *****************************************************************************/
package py4j;

import java.io.BufferedReader;
import java.io.Closeable;
import java.io.IOException;
import java.net.ServerSocket;
import java.net.Socket;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * <p>
 * Utility class used to perform network operations.
 * </p>
 * 
 * @author Barthelemy Dagenais
 * 
 */
public class NetworkUtil {

	private final static Logger logger = Logger.getLogger(NetworkUtil.class.getName());

	/**
	 *
	 * @param reader
	 * @param addSpace
	 * @return A non-null String with an optional space if it is empty.
	 * @throws IOException
	 */
	public static String safeReadLine(BufferedReader reader, boolean addSpace) throws IOException {
		String line = reader.readLine();
		if (line == null || (line.length() == 0 && addSpace)) {
			if (addSpace) {
				line = " ";
			} else {
				line = "";
			}
		}

		return line;
	}

	/**
	 *
	 * @param reader
	 * @return A String of at least one character (space if null or empty).
	 * @throws IOException
	 */
	public static String safeReadLine(BufferedReader reader) throws IOException {
		return safeReadLine(reader, true);
	}

	public static void quietlyClose(Closeable closeable) {
		try {
			if (closeable != null) {
				closeable.close();
			}
		} catch (Exception e) {
			logger.log(Level.FINE, "Closeable cannot be closed.", e);
		}
	}

	public static void quietlyClose(ServerSocket closeable) {
		try {
			if (closeable != null) {
				closeable.close();
			}
		} catch (Exception e) {
			logger.log(Level.FINE, "Socket cannot be closed.", e);
		}
	}

	public static void quietlyClose(Socket closeable) {
		try {
			if (closeable != null) {
				closeable.shutdownInput();
				closeable.shutdownOutput();
				closeable.close();
			}
		} catch (Exception e) {
			logger.log(Level.FINE, "Socket cannot be closed.", e);
		}
	}

}