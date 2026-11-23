package com.specdriven.notes.data.document;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.nio.charset.StandardCharsets;

public final class TestDocumentProvider extends ContentProvider {
    private static final int OVERSIZE_BYTES = 1_048_577;
    private static final int EXACT_LIMIT_BYTES = 1_048_576;
    private static final String WRITTEN_FILE = "written-document.txt";

    @Override
    public boolean onCreate() {
        return true;
    }

    @Override
    public String getType(Uri uri) {
        return "text/plain";
    }

    @Override
    public Cursor query(
            Uri uri,
            String[] projection,
            String selection,
            String[] selectionArgs,
            String sortOrder
    ) {
        String[] columns = projection != null
                ? projection
                : new String[]{OpenableColumns.DISPLAY_NAME};
        MatrixCursor cursor = new MatrixCursor(columns);
        Object[] row = new Object[columns.length];
        for (int index = 0; index < columns.length; index++) {
            if (OpenableColumns.DISPLAY_NAME.equals(columns[index])) {
                row[index] = uri.getQueryParameter("name");
            }
        }
        cursor.addRow(row);
        return cursor;
    }

    @Override
    public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        String path = uri.getPath();
        if ("/read/text".equals(path)) {
            String value = uri.getQueryParameter("value");
            return openReadFile(
                    value == null ? new byte[0] : value.getBytes(StandardCharsets.UTF_8)
            );
        }
        if ("/read/bom".equals(path)) {
            String value = uri.getQueryParameter("value");
            byte[] content = value == null
                    ? new byte[0]
                    : value.getBytes(StandardCharsets.UTF_8);
            byte[] bytes = new byte[content.length + 3];
            bytes[0] = (byte) 0xEF;
            bytes[1] = (byte) 0xBB;
            bytes[2] = (byte) 0xBF;
            System.arraycopy(content, 0, bytes, 3, content.length);
            return openReadFile(bytes);
        }
        if ("/read/malformed".equals(path)) {
            return openReadFile(new byte[]{(byte) 0xC3, 0x28});
        }
        if ("/read/oversize".equals(path)) {
            return openReadFile(new byte[OVERSIZE_BYTES]);
        }
        if ("/read/exact-limit".equals(path)) {
            byte[] bytes = new byte[EXACT_LIMIT_BYTES];
            java.util.Arrays.fill(bytes, (byte) 'a');
            return openReadFile(bytes);
        }
        if ("/write".equals(path)) {
            return ParcelFileDescriptor.open(
                    writtenFile(),
                    ParcelFileDescriptor.MODE_CREATE
                            | ParcelFileDescriptor.MODE_TRUNCATE
                            | ParcelFileDescriptor.MODE_READ_WRITE
            );
        }
        if ("/write/interrupted".equals(path)) {
            try {
                ParcelFileDescriptor[] pipe = ParcelFileDescriptor.createReliablePipe();
                pipe[0].closeWithError("Controlled interrupted write");
                return pipe[1];
            } catch (IOException exception) {
                throw new FileNotFoundException(exception.getMessage());
            }
        }
        if ("/written".equals(path)) {
            return ParcelFileDescriptor.open(writtenFile(), ParcelFileDescriptor.MODE_READ_ONLY);
        }
        throw new FileNotFoundException("Controlled provider failure");
    }

    @Override
    public Uri insert(Uri uri, ContentValues values) {
        return null;
    }

    @Override
    public int delete(Uri uri, String selection, String[] selectionArgs) {
        return writtenFile().delete() ? 1 : 0;
    }

    @Override
    public int update(Uri uri, ContentValues values, String selection, String[] selectionArgs) {
        return 0;
    }

    private ParcelFileDescriptor openReadFile(byte[] bytes) throws FileNotFoundException {
        try {
            File file = File.createTempFile("document-read-", ".txt", getContext().getCacheDir());
            java.nio.file.Files.write(file.toPath(), bytes);
            return ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY);
        } catch (IOException exception) {
            throw new FileNotFoundException(exception.getMessage());
        }
    }

    private File writtenFile() {
        return new File(getContext().getCacheDir(), WRITTEN_FILE);
    }
}
