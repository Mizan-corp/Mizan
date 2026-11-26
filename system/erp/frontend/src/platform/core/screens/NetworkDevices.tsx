/**
 * Settings → devices on the network (#88): on a LAN install, the addresses tills open and a QR
 * code to scan, plus the one-time certificate step. Single-device installs say why there's none.
 */
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import QRCode from "qrcode";
import { Check, Copy, Download, MonitorSmartphone, Wifi } from "lucide-react";
import { api } from "@/lib/api";
import { Card } from "@/components/kit/card";
import { Button } from "@/components/kit/button";
import { Spinner } from "@/components/ui";

interface Network {
  mode: "desktop" | "lan" | string;
  hostname: string;
  mdns: string | null;
  addresses: string[];
  ca_certificate: boolean;
}

export function NetworkDevices() {
  const q = useQuery({ queryKey: ["onprem-network"], queryFn: () => api.get<Network>("/onprem/network") });
  const [selected, setSelected] = useState<string | null>(null);
  const [qr, setQr] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  const port = window.location.port ? `:${window.location.port}` : "";
  const scheme = window.location.protocol.replace(":", "");
  const urls = q.data
    ? [...q.data.addresses, ...(q.data.mdns ? [q.data.mdns] : []), q.data.hostname].map((h) => `${scheme}://${h}${port}`)
    : [];
  const main = selected ?? urls[0] ?? null;

  useEffect(() => {
    if (!main) return;
    QRCode.toDataURL(main, { margin: 1, width: 220, color: { dark: "#35151D", light: "#FFFFFF" } }).then(setQr, () => setQr(null));
  }, [main]);

  async function copy(url: string) {
    await navigator.clipboard?.writeText(url).catch(() => {});
    setCopied(url);
    setTimeout(() => setCopied(null), 1500);
  }

  if (q.isPending) return <div className="flex justify-center p-10"><Spinner /></div>;
  if (q.isError || !q.data) return <Card className="p-6 text-sm text-muted-foreground">تعذر قراءة إعدادات الشبكة.</Card>;

  if (q.data.mode !== "lan") {
    return (
      <Card className="flex items-start gap-3 p-6 text-sm">
        <MonitorSmartphone className="mt-0.5 size-5 text-primary" />
        <div>
          <p className="font-semibold text-foreground">نسخة جهاز واحد</p>
          <p className="mt-1 text-muted-foreground">
            تعمل ميزان على هذا الجهاز فقط ولا تتصل بها أجهزة أخرى. لربط أجهزة كاشير متعددة، اطلب نسخة «شبكة محلية» من لوحة المالك.
          </p>
        </div>
      </Card>
    );
  }

  return (
    <Card className="space-y-5 p-6">
      <div className="flex items-center gap-2">
        <Wifi className="size-5 text-primary" />
        <h2 className="text-base font-bold text-foreground">ربط أجهزة الكاشير والمكاتب</h2>
      </div>
      <div className="flex flex-col gap-6 md:flex-row-reverse md:items-start md:justify-end">
        {qr && main && (
          <figure className="shrink-0 text-center">
            <img src={qr} alt={`رمز QR للعنوان ${main}`} className="size-44 rounded-xl ring-1 ring-border" />
            <figcaption className="mt-2 text-xs text-muted-foreground">امسحه بكاميرا الجهاز</figcaption>
          </figure>
        )}
        <div className="min-w-0 flex-1 space-y-4 text-sm">
          <ol className="list-decimal space-y-1.5 ps-5 text-muted-foreground">
            <li>وصّل الجهاز بنفس شبكة هذا الخادم (الواي فاي أو الكابل).</li>
            <li>افتح أحد العناوين التالية في متصفحه، أو امسح الرمز.</li>
            <li>مرة واحدة على كل جهاز: من صفحة الدخول اضغط «ثبّت شهادة الأمان» واتبع الخطوات، ليعمل البيع بدون إنترنت.</li>
          </ol>
          <ul className="divide-y divide-border rounded-xl border border-border">
            {urls.map((url) => (
              <li key={url} className={`flex items-center justify-between gap-2 px-3 py-2 ${url === main ? "bg-primary/5" : ""}`}>
                <button type="button" onClick={() => setSelected(url)} className="code min-w-0 truncate text-start text-foreground" dir="ltr"
                        aria-pressed={url === main} title="اعرض رمز QR لهذا العنوان">
                  {url}
                </button>
                <Button size="sm" variant="ghost" onClick={() => copy(url)} aria-label={`انسخ ${url}`}>
                  {copied === url ? <Check /> : <Copy />}
                </Button>
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted-foreground">
            العنوان بالأرقام يعمل على كل الأجهزة. <span className="code" dir="ltr">mizan.local</span> واسم الجهاز يعملان على معظمها، ويبقيان كما هما لو تغيّر عنوان الخادم.
          </p>
          {q.data.ca_certificate && (
            <Button variant="outline" size="sm" render={<a href="/api/onprem/ca.crt" download="mizan-ca.crt" />}>
              <Download /> تنزيل شهادة الأمان
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
