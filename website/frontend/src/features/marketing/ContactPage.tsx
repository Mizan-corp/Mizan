import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Send,
  CheckCircle2,
  Headphones,
  MessageCircle,
  Phone,
  Clock,
  ShieldCheck,
} from "lucide-react";
import { Button } from "@/components/kit/button";
import { Input } from "@/components/kit/input";
import { MarketingLayout } from "./MarketingLayout";
import { toast } from "sonner";
import { sound } from "@/lib/sound";
import { useTranslation } from "@/i18n";
import { assetUrl } from "@/lib/utils";
import { MizanMagnetic } from "@/components/motion/MizanMagnetic";
import { Link } from "react-router-dom";
import { BUSINESS, PHONE_HREF, whatsappHref } from "@app/features/legal/business";

export default function ContactPage() {
  const { locale } = useTranslation();
  const isAr = locale === "ar";

  const [inquiryType, setInquiryType] = useState<"demo" | "enterprise" | "migration" | "support">("demo");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [industry, setIndustry] = useState("retail");
  const [industryLabel, setIndustryLabel] = useState("");
  const [message, setMessage] = useState("");
  const [isSuccess, setIsSuccess] = useState(false);

  const INQUIRY_LABEL = {
    demo: isAr ? "عرض توضيحي" : "Demo",
    enterprise: isAr ? "باقة المؤسسات" : "Enterprise plan",
    migration: isAr ? "نقل البيانات" : "Data migration",
    support: isAr ? "دعم فني" : "Support",
  } as const;

  /** No mailbox behind this form: it opens WhatsApp with the message written out. */
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName.trim() || !phone.trim()) {
      toast.error(isAr ? "اكتب اسمك ورقم هاتفك" : "Please enter your name and phone number");
      return;
    }
    const lines = [
      isAr ? `طلب: ${INQUIRY_LABEL[inquiryType]}` : `Request: ${INQUIRY_LABEL[inquiryType]}`,
      `${isAr ? "الاسم" : "Name"}: ${fullName.trim()}`,
      `${isAr ? "الهاتف" : "Phone"}: ${phone.trim()}`,
      email.trim() && `${isAr ? "البريد" : "Email"}: ${email.trim()}`,
      companyName.trim() && `${isAr ? "المنشأة" : "Business"}: ${companyName.trim()}`,
      industryLabel && `${isAr ? "النشاط" : "Industry"}: ${industryLabel}`,
      message.trim() && `\n${message.trim()}`,
    ].filter(Boolean);
    window.open(whatsappHref(lines.join("\n")), "_blank", "noopener,noreferrer");
    setIsSuccess(true);
    try {
      sound.success();
    } catch {}
  };

  return (
    <MarketingLayout>
      <div className="py-16 sm:py-24 bg-[#FAF6F0] text-[#262321] transition-colors">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 space-y-16">
          {/* 1. Header */}
          <div className="mx-auto max-w-3xl text-center space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full border border-[#E7D6C1] bg-white/80 px-4 py-1.5 text-xs font-semibold text-[#651E2C] shadow-xs">
              <Headphones className="size-3.5 text-[#B86B76]" />
              <span>{isAr ? "فريق الاستشارات الهندسية والمبيعات" : "Engineering Consultation & Advisory"}</span>
            </div>

            <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl font-normal tracking-tight text-[#262321] leading-[1.15]">
              {isAr ? (
                <>
                  لنناقش التوازن التشغيلي <br />
                  <span className="italic text-[#B86B76]">والمعماري لمنشأتك</span>
                </>
              ) : (
                <>
                  Let's discuss the architectural <br />
                  <span className="italic text-[#B86B76]">balance of your enterprise</span>
                </>
              )}
            </h1>

            <p className="mx-auto max-w-2xl text-base text-[#77716E] font-body leading-relaxed">
              {isAr
                ? "سواء كنت ترغب في جدولة عرض توضيحي حي (Live Demo)، بحث متطلبات الربط السحابي، أو استكشاف خطط المؤسسات، مهندسونا مستعدون لمساعدتك."
                : "Whether scheduling a live architectural walkthrough, planning legacy data migration, or configuring custom enterprise infrastructure, we are here."}
            </p>
          </div>

          {/* 2. Split Contact Section */}
          <div className="grid grid-cols-1 gap-12 lg:grid-cols-12 items-start">
            {/* Left Column: Architectural Info Card */}
            <div className="lg:col-span-5 space-y-6">
              <div className="rounded-3xl border border-[#E7D6C1] bg-white p-8 shadow-xs space-y-6">
                <div className="relative rounded-2xl overflow-hidden border border-[#E7D6C1] aspect-[16/10] bg-[#35151D]">
                  <img
                    src={assetUrl("assets/marketing/contact-building.jpg")}
                    alt="Mizan Headquarters"
                    className="w-full h-full object-cover opacity-90 hover:scale-105 transition-transform duration-500"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-[#35151D]/80 via-transparent to-transparent" />
                  <div className="absolute bottom-4 start-4 text-white">
                    <span className="text-[10px] uppercase font-bold tracking-widest text-[#B86B76]">
                      {isAr ? "نعمل من" : "Based in"}
                    </span>
                    <h3 className="font-display text-lg font-normal">
                      {BUSINESS.city[isAr ? "ar" : "en"]}
                    </h3>
                  </div>
                </div>

                <div className="space-y-4 pt-2 text-xs">
                  <div className="flex items-start gap-3">
                    <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-[#FAF6F0] text-[#651E2C] border border-[#E7D6C1]">
                      <MessageCircle className="size-4" />
                    </div>
                    <div>
                      <span className="text-[#77716E] block font-medium">
                        {isAr ? "واتساب (الأسرع):" : "WhatsApp (fastest):"}
                      </span>
                      <a href={whatsappHref()} target="_blank" rel="noopener noreferrer" dir="ltr" className="font-mono font-bold text-[#651E2C] hover:underline">
                        {BUSINESS.phoneDisplay}
                      </a>
                    </div>
                  </div>

                  <div className="flex items-start gap-3">
                    <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-[#FAF6F0] text-[#651E2C] border border-[#E7D6C1]">
                      <Phone className="size-4" />
                    </div>
                    <div>
                      <span className="text-[#77716E] block font-medium">
                        {isAr ? "اتصال هاتفي:" : "Phone:"}
                      </span>
                      <a href={PHONE_HREF} dir="ltr" className="font-mono font-bold text-[#262321] hover:underline">
                        {BUSINESS.phoneDisplay}
                      </a>
                    </div>
                  </div>

                  <div className="flex items-start gap-3">
                    <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-[#FAF6F0] text-[#651E2C] border border-[#E7D6C1]">
                      <Clock className="size-4" />
                    </div>
                    <div>
                      <span className="text-[#77716E] block font-medium">
                        {isAr ? "مواعيد الرد:" : "When we reply:"}
                      </span>
                      <span className="text-[#262321] font-semibold">
                        {isAr ? "خلال أيام وساعات العمل" : "During business days and hours"}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-start gap-3">
                    <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-[#FAF6F0] text-[#651E2C] border border-[#E7D6C1]">
                      <ShieldCheck className="size-4" />
                    </div>
                    <div>
                      <span className="text-[#77716E] block font-medium">
                        {isAr ? "الشروط والخصوصية:" : "Terms & privacy:"}
                      </span>
                      <span className="flex flex-wrap gap-x-3 text-[#262321]">
                        <Link to="/terms" className="hover:text-[#651E2C] hover:underline">{isAr ? "شروط الاستخدام" : "Terms"}</Link>
                        <Link to="/privacy" className="hover:text-[#651E2C] hover:underline">{isAr ? "الخصوصية" : "Privacy"}</Link>
                        <Link to="/refund-policy" className="hover:text-[#651E2C] hover:underline">{isAr ? "الاسترداد" : "Refunds"}</Link>
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Right Column: Contact & Booking Form */}
            <div className="lg:col-span-7">
              <div className="rounded-3xl border border-[#E7D6C1] bg-white p-8 sm:p-10 shadow-xs">
                <AnimatePresence mode="wait">
                  {isSuccess ? (
                    <motion.div
                      key="success"
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                      className="py-12 text-center space-y-4"
                    >
                      <div className="mx-auto flex size-16 items-center justify-center rounded-full bg-[#FAF6F0] text-[#651E2C] border-2 border-[#E7D6C1]">
                        <CheckCircle2 className="size-8" />
                      </div>
                      <h3 className="font-display text-2xl font-normal text-[#262321]">
                        {isAr ? "أكمل الإرسال في واتساب" : "Finish sending in WhatsApp"}
                      </h3>
                      <p className="mx-auto max-w-md text-xs sm:text-sm text-[#77716E] leading-relaxed">
                        {isAr
                          ? "فتحنا واتساب برسالتك جاهزة؛ اضغط إرسال هناك. لم يُفتح؟ راسلنا مباشرة على "
                          : "We opened WhatsApp with your message ready; press send there. Didn't open? Message us at "}
                        <a href={whatsappHref()} target="_blank" rel="noopener noreferrer" dir="ltr" className="font-semibold text-[#651E2C] hover:underline">
                          {BUSINESS.phoneDisplay}
                        </a>
                      </p>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setIsSuccess(false);
                          setMessage("");
                        }}
                        className="border-[#E7D6C1] text-xs mt-2"
                      >
                        {isAr ? "رسالة أخرى" : "Another message"}
                      </Button>
                    </motion.div>
                  ) : (
                    <motion.form
                      key="form"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      onSubmit={handleSubmit}
                      className="space-y-6"
                    >
                      {/* Inquiry Type Tabs */}
                      <div className="space-y-2">
                        <label className="text-xs font-bold text-[#262321]">
                          {isAr ? "نوع الطلب أو الاستشارة:" : "Nature of Inquiry:"}
                        </label>
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                          {[
                            { id: "demo", labelAr: "عرض حي (Live Demo)", labelEn: "Live Demo" },
                            { id: "enterprise", labelAr: "باقة المؤسسات", labelEn: "Enterprise" },
                            { id: "migration", labelAr: "نقل البيانات", labelEn: "Data Migration" },
                            { id: "support", labelAr: "دعم فني واستشارة", labelEn: "Technical Support" },
                          ].map((t) => (
                            <button
                              key={t.id}
                              type="button"
                              onClick={() => setInquiryType(t.id as any)}
                              className={`relative rounded-xl border py-2.5 px-3 text-center transition-colors ${
                                inquiryType === t.id
                                  ? "border-[#651E2C] text-[#651E2C] font-bold"
                                  : "border-[#E7D6C1] bg-[#FAF6F0] text-[#77716E] hover:border-[#651E2C]/40"
                              }`}
                            >
                              {inquiryType === t.id && (
                                <motion.div
                                  layoutId="inquiryPillHighlight"
                                  transition={{ type: "spring", stiffness: 450, damping: 30 }}
                                  className="absolute inset-0 rounded-xl bg-[#651E2C]/10 border border-[#651E2C] z-[-1]"
                                />
                              )}
                              <span>{isAr ? t.labelAr : t.labelEn}</span>
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* Fields Row 1 */}
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="space-y-1.5">
                          <label className="text-xs font-bold text-[#262321]">
                            {isAr ? "الاسم الكامل *" : "Full Name *"}
                          </label>
                          <Input
                            type="text"
                            required
                            value={fullName}
                            onChange={(e) => setFullName(e.target.value)}
                            placeholder={isAr ? "مثال: م. أحمد منصور" : "e.g. Johnathan Miller"}
                            className="border-[#E7D6C1] bg-[#FAF6F0] text-xs py-2"
                          />
                        </div>

                        <div className="space-y-1.5">
                          <label className="text-xs font-bold text-[#262321]">
                            {isAr ? "البريد الإلكتروني (اختياري)" : "Email (optional)"}
                          </label>
                          <Input
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            placeholder="name@company.com"
                            className="border-[#E7D6C1] bg-[#FAF6F0] text-xs py-2 font-mono"
                          />
                        </div>
                      </div>

                      {/* Fields Row 2 */}
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="space-y-1.5">
                          <label className="text-xs font-bold text-[#262321]">
                            {isAr ? "رقم الهاتف / واتساب *" : "Phone / WhatsApp *"}
                          </label>
                          <Input
                            type="tel"
                            required
                            value={phone}
                            onChange={(e) => setPhone(e.target.value)}
                            placeholder="+20 100 123 4567"
                            className="border-[#E7D6C1] bg-[#FAF6F0] text-xs py-2 font-mono"
                          />
                        </div>

                        <div className="space-y-1.5">
                          <label className="text-xs font-bold text-[#262321]">
                            {isAr ? "اسم المنشأة أو الشركة" : "Company / Enterprise Name"}
                          </label>
                          <Input
                            type="text"
                            value={companyName}
                            onChange={(e) => setCompanyName(e.target.value)}
                            placeholder={isAr ? "مثال: مجموعة المنار للتجارة" : "e.g. Apex Global Trade"}
                            className="border-[#E7D6C1] bg-[#FAF6F0] text-xs py-2"
                          />
                        </div>
                      </div>

                      {/* Industry Selector */}
                      <div className="space-y-1.5">
                        <label className="text-xs font-bold text-[#262321]">
                          {isAr ? "القطاع التجاري الأساسي:" : "Primary Business Vertical:"}
                        </label>
                        <select
                          value={industry}
                          onChange={(e) => {
                            setIndustry(e.target.value);
                            setIndustryLabel(e.target.selectedOptions[0]?.text ?? "");
                          }}
                          className="w-full rounded-xl border border-[#E7D6C1] bg-[#FAF6F0] px-3.5 py-2.5 text-xs text-[#262321] focus:border-[#651E2C] focus:outline-hidden"
                        >
                          <option value="retail">{isAr ? "التجزئة والمتاجر والمعارض (Retail & Trade)" : "Retail & Commercial Showrooms"}</option>
                          <option value="materials">{isAr ? "مواد البناء والتشطيبات والعدد (Building Materials)" : "Building Materials & Hardware"}</option>
                          <option value="hospitality">{isAr ? "المطاعم والكافيهات وسلاسل الضيافة (Hospitality & KDS)" : "Restaurants, Cafes & Food Chains"}</option>
                          <option value="manufacturing">{isAr ? "التصنيع وتجهيز المواد الخام (Manufacturing & Assembly)" : "Discrete Manufacturing & Assembly"}</option>
                          <option value="healthcare">{isAr ? "المجمعات الطبية والعيادات والصيدليات (Healthcare & Clinics)" : "Healthcare & Medical Polyclinics"}</option>
                          <option value="distribution">{isAr ? "التوزيع وسلاسل الإمداد والأسطول (Logistics & Fleet)" : "Distribution, Warehousing & Fleet"}</option>
                        </select>
                      </div>

                      {/* Message Textarea */}
                      <div className="space-y-1.5">
                        <label className="text-xs font-bold text-[#262321]">
                          {isAr ? "تفاصيل إضافية أو متطلبات خاصة (اختياري):" : "Specific Requirements / Notes (Optional):"}
                        </label>
                        <textarea
                          rows={4}
                          value={message}
                          onChange={(e) => setMessage(e.target.value)}
                          placeholder={
                            isAr
                              ? "عدد الفروع الحالية، أجهزة الكاشير المستخدمة، أو طبيعة قواعد البيانات الحالية..."
                              : "Current branches, hardware setups, or current accounting system in place..."
                          }
                          className="w-full rounded-xl border border-[#E7D6C1] bg-[#FAF6F0] p-3 text-xs text-[#262321] placeholder:text-[#77716E] focus:border-[#651E2C] focus:outline-hidden"
                        />
                      </div>

                      <MizanMagnetic className="w-full">
                        <Button
                          type="submit"
                          className="w-full bg-[#651E2C] text-white hover:bg-[#521723] rounded-xl py-3 text-xs font-bold shadow-md transition-all flex items-center justify-center gap-2"
                        >
                          <Send className="size-3.5" />
                          <span>{isAr ? "إرسال عبر واتساب" : "Send via WhatsApp"}</span>
                        </Button>
                      </MizanMagnetic>
                    </motion.form>
                  )}
                </AnimatePresence>
              </div>
            </div>
          </div>
        </div>
      </div>
    </MarketingLayout>
  );
}
