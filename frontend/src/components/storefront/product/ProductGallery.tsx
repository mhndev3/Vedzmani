"use client";

import Image from "next/image";
import { useEffect, useRef, useState, type TouchEvent } from "react";

type GalleryImage = {
  url: string;
  alt_text: string;
  position: number;
  is_primary: boolean;
  width: number;
  height: number;
};

export function ProductGallery({
  images,
  productName,
  colorName,
  variantKey,
  labels,
}: {
  images: GalleryImage[];
  productName: string;
  colorName: string;
  variantKey: string;
  labels: { gallery: string; previous: string; next: string; slide: string; noImages: string };
}) {
  const imageKey = variantKey + ":" + images.map((image) => image.url + "|" + image.alt_text).join(";");
  const [displayImages, setDisplayImages] = useState(images);
  const [activeIndex, setActiveIndex] = useState(0);
  const [fading, setFading] = useState(false);
  const previousKey = useRef(imageKey);
  const touchStartX = useRef<number | null>(null);

  useEffect(() => {
    if (previousKey.current === imageKey) return;
    previousKey.current = imageKey;
    setFading(true);
    const timeout = window.setTimeout(() => {
      setDisplayImages(images);
      setActiveIndex(0);
      window.requestAnimationFrame(() => setFading(false));
    }, 150);
    return () => window.clearTimeout(timeout);
  }, [imageKey, images]);

  const hasImages = displayImages.length > 0;
  const hasMultiple = displayImages.length > 1;
  const current = displayImages[activeIndex] ?? displayImages[0];

  function previous() {
    setActiveIndex((index) => (index === 0 ? displayImages.length - 1 : index - 1));
  }

  function next() {
    setActiveIndex((index) => (index + 1) % displayImages.length);
  }

  function handleTouchEnd(event: TouchEvent<HTMLDivElement>) {
    const start = touchStartX.current;
    touchStartX.current = null;
    if (start === null || !hasMultiple) return;
    const end = event.changedTouches[0]?.clientX;
    if (end === undefined || Math.abs(end - start) < 45) return;
    if (end < start) next();
    else previous();
  }

  return (
    <section aria-label={labels.gallery} className="min-w-0">
      {hasImages ? (
        <>
          <div
            className="relative aspect-[3/4] overflow-hidden rounded-xl bg-muted"
            onTouchStart={(event) => {
              touchStartX.current = event.changedTouches[0]?.clientX ?? null;
            }}
            onTouchEnd={handleTouchEnd}
            onTouchCancel={() => {
              touchStartX.current = null;
            }}
          >
            <Image
              key={current.url}
              src={current.url}
              alt={current.alt_text || (productName + (colorName ? " - " + colorName : ""))}
              fill
              sizes="(min-width:768px) 50vw, 100vw"
              unoptimized
              priority={activeIndex === 0}
              fetchPriority={activeIndex === 0 ? "high" : "auto"}
              className={"object-contain transition-opacity duration-150 ease-in-out motion-reduce:transition-none " + (fading ? "opacity-0" : "opacity-100")}
            />

            {hasMultiple && (
              <>
                <button
                  type="button"
                  onClick={previous}
                  aria-label={labels.previous}
                  className="absolute start-3 top-1/2 inline-flex size-10 -translate-y-1/2 items-center justify-center rounded-full border border-border/70 bg-background/85 text-2xl shadow-sm backdrop-blur transition hover:bg-background focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                >
                  <span aria-hidden="true">‹</span>
                </button>
                <button
                  type="button"
                  onClick={next}
                  aria-label={labels.next}
                  className="absolute end-3 top-1/2 inline-flex size-10 -translate-y-1/2 items-center justify-center rounded-full border border-border/70 bg-background/85 text-2xl shadow-sm backdrop-blur transition hover:bg-background focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                >
                  <span aria-hidden="true">›</span>
                </button>
              </>
            )}
          </div>

          {hasMultiple && (
            <div className="mt-3 flex items-center justify-center gap-2" aria-label="پیمایش تصاویر">
              {displayImages.map((image, index) => (
                <button
                  key={image.url}
                  type="button"
                  onClick={() => setActiveIndex(index)}
                  aria-label={labels.slide.replace("{index}", String(index + 1))}
                  aria-current={activeIndex === index ? "true" : undefined}
                  className={"h-2.5 rounded-full transition-all focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring " + (activeIndex === index ? "w-7 bg-primary" : "w-2.5 bg-muted-foreground/40 hover:bg-muted-foreground/70")}
                />
              ))}
            </div>
          )}

          <p className="sr-only" aria-live="polite">
            {activeIndex + 1} / {displayImages.length}
          </p>
        </>
      ) : (
        <div className="flex aspect-[3/4] items-center justify-center rounded-xl bg-muted text-sm text-muted-foreground">
          {labels.noImages}
        </div>
      )}
    </section>
  );
}
