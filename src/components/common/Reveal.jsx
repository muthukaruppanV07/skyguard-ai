import { motion } from "framer-motion";

const variants = {
  hidden: { opacity: 0, y: 26 },
  visible: { opacity: 1, y: 0 },
};

/**
 * Fades + slides content in when it enters the viewport.
 * Pass `delay` (in steps of ~0.08s) to stagger grids.
 */
export default function Reveal({ children, delay = 0, className }) {
  return (
    <motion.div
      className={className}
      variants={variants}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.55, ease: "easeOut", delay: delay * 0.08 }}
    >
      {children}
    </motion.div>
  );
}