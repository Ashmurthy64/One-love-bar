/* Direct multipart upload: preserve media bytes and report transport progress. */
function uploadDashboardMedia({ url, file, token, maxMiB = 60, onProgress = () => {}, xhrFactory = () => new XMLHttpRequest() }) {
  if (file.size > maxMiB * 1024 * 1024) return Promise.reject(new Error(`File too large (max ${maxMiB} MiB). Choose a smaller file.`));
  return new Promise((resolve, reject) => {
    const xhr = xhrFactory();
    xhr.open("POST", url);
    xhr.timeout = 10 * 60 * 1000;
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = event => {
      if (event.lengthComputable) onProgress(Math.min(100, Math.round(event.loaded / event.total * 100)));
    };
    xhr.onload = () => {
      let data;
      try { data = JSON.parse(xhr.responseText); } catch (_) { /* Proxy errors may be HTML. */ }
      if (xhr.status >= 200 && xhr.status < 300 && data?.filename) return resolve(data);
      const message = data?.error || (xhr.status === 413
        ? "File too large. Videos can be up to 60 MiB; images up to 20 MiB."
        : xhr.status === 401 ? "Your session expired. Sign in again and retry the upload."
        : `Upload failed (HTTP ${xhr.status}). Please retry.`);
      reject(new Error(message));
    };
    xhr.onerror = () => reject(new Error("Upload interrupted. Check your connection and retry."));
    xhr.ontimeout = () => reject(new Error("Upload timed out. Check your connection and retry."));
    xhr.onabort = () => reject(new Error("Upload cancelled. Choose the file to try again."));
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}
if (typeof module !== "undefined" && module.exports) module.exports = { uploadDashboardMedia };
