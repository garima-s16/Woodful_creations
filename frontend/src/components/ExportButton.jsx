import React from "react";

export default function ExportButton({ url, filename, label="Download" }) {
  const handleDownload = async () => {
    try {
      const res = await fetch(url, {
        method: "GET",
        credentials: "include", // sends the HttpOnly auth cookie
      });
      if (!res.ok) throw new Error("Download failed");
      const blob = await res.blob();
      const link = document.createElement("a");
      link.href = window.URL.createObjectURL(blob);
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      alert("Export failed: " + err.message);
    }
  };
  return <button onClick={handleDownload}>{label}</button>;
}
