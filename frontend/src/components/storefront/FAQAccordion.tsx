"use client";

import { useState } from "react";

const questions = [
  {
    question: "چگونه می‌توانیم سفارش خود را ثبت کنیم؟",
    answer:
      "برای ثبت سفارش، وارد وب‌سایت ودزمانی شوید، محصول موردنظر خود را انتخاب کنید و پس از مشخص کردن رنگ و سایز، آن را به سبد خرید اضافه کنید. سپس با ورود به سبد خرید، مراحل تکمیل سفارش را دنبال کنید.",
  },
  {
    question: "اگر برای انتخاب سایز مطمئن نبودم، چه‌کار کنم؟",
    answer:
      "موارد گفته‌شده در جدول سایزها را اندازه‌گیری کنید و بعد از بررسی جدول سایزبندی، سایز مناسب را انتخاب کنید.",
  },
  {
    question: "به‌جز وب‌سایت، از چه طریقی می‌توانیم سفارش خود را ثبت کنیم؟",
    answer:
      "علاوه بر وب‌سایت، امکان ثبت سفارش از طریق صفحه اینستاگرام ودزمانی نیز وجود دارد.",
    instagram: true,
  },
  {
    question: "آیا امکان تغییر یا لغو سفارش وجود دارد؟",
    answer:
      "خیر. پس از تکمیل فرایند خرید، امکان تغییر یا لغو سفارش وجود نخواهد داشت.",
  },
  {
    question: "آیا امکان تعویض کالا پس از دریافت بسته وجود دارد؟",
    answer:
      "بله. پس از بررسی مشکل و تأیید آن، امکان تعویض کالا وجود دارد.",
  },
  {
    question: "روش‌های ارسال سفارش چیست؟",
    answer: "ارسال سفارش‌ها از طریق پست و تیپاکس انجام می‌شود.",
  },
  {
    question: "هزینه ارسال چگونه محاسبه می‌شود؟",
    answer:
      "هزینه ارسال با توجه به مقصد سفارش و روش ارسال محاسبه می‌شود و در مرحله ثبت سفارش به مشتری نمایش داده خواهد شد.",
  },
];

function InstagramIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className="h-5 w-5"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
    >
      <rect x="3" y="3" width="18" height="18" rx="5" />
      <circle cx="12" cy="12" r="4" />
      <circle cx="17.5" cy="6.5" r="0.8" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function FAQAccordion() {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  return (
    <div className="space-y-3" dir="rtl">
      {questions.map((item, index) => {
        const isOpen = openIndex === index;
        const answerId = `faq-answer-${index}`;

        return (
          <section
            key={item.question}
            className="overflow-hidden rounded-2xl border border-border bg-background shadow-sm transition-colors"
          >
            <h2>
              <button
                type="button"
                aria-expanded={isOpen}
                aria-controls={answerId}
                onClick={() => setOpenIndex(isOpen ? null : index)}
                className="flex w-full items-center justify-between gap-4 px-5 py-5 text-right text-sm font-semibold leading-7 transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-foreground sm:px-6 sm:text-base"
              >
                <span>{item.question}</span>
                <svg
                  aria-hidden="true"
                  viewBox="0 0 24 24"
                  className={`h-5 w-5 shrink-0 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`}
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="m6 9 6 6 6-6" />
                </svg>
              </button>
            </h2>

            {isOpen && (
              <div
                id={answerId}
                className="border-t border-border px-5 py-5 text-sm leading-8 text-muted-foreground sm:px-6 sm:text-base"
              >
                <p>{item.answer}</p>
                {item.instagram && (
                  <a
                    href="https://www.instagram.com/vedzmani/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-3 inline-flex items-center gap-2 font-medium text-foreground underline decoration-border underline-offset-4 transition-colors hover:decoration-foreground"
                    aria-label="باز کردن صفحه اینستاگرام ودزمانی"
                  >
                    <InstagramIcon />
                    <span>لینک اینستاگرام</span>
                  </a>
                )}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}
