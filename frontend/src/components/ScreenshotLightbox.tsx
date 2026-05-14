import Lightbox from 'yet-another-react-lightbox'
import 'yet-another-react-lightbox/styles.css'

interface Props {
  images: { src: string; alt?: string }[]
  index: number | null
  onClose: () => void
}

export default function ScreenshotLightbox({ images, index, onClose }: Props) {
  return (
    <Lightbox
      open={index !== null}
      index={index ?? 0}
      close={onClose}
      slides={images.map((img) => ({ src: img.src, alt: img.alt }))}
    />
  )
}
