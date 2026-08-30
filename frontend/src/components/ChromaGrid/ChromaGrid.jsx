/**
 * ChromaGrid — React Bits component with GSAP spotlight effect.
 *
 * Props:
 *   items       Array<ChromaItem>  — Cards to display. Uses demo data if empty.
 *   className   string             — Extra CSS classes for the grid container.
 *   radius      number             — Spotlight radius in px (default 300).
 *   columns     number             — Grid columns (default 3).
 *   rows        number             — Grid rows (default 2).
 *   damping     number             — GSAP cursor-follow duration (default 0.45).
 *   fadeOut     number             — Fade-out duration on mouse leave (default 0.6).
 *   ease        string             — GSAP ease (default 'power3.out').
 */
'use client';

import { useRef, useEffect } from 'react';
import { gsap } from 'gsap';
import './ChromaGrid.css';

/**
 * @typedef {{
 *   image: string,
 *   title: string,
 *   subtitle: string,
 *   handle: string,
 *   borderColor: string,
 *   gradient: string,
 *   url: string,
 * }} ChromaItem
 */

const demo = [
  {
    image: 'https://i.pravatar.cc/300?img=8',
    title: 'Alex Rivera',
    subtitle: 'Full Stack Developer',
    handle: '@alexrivera',
    borderColor: '#4F46E5',
    gradient: 'linear-gradient(145deg, #4F46E5, #000)',
    url: 'https://github.com/',
  },
  {
    image: 'https://i.pravatar.cc/300?img=11',
    title: 'Jordan Chen',
    subtitle: 'DevOps Engineer',
    handle: '@jordanchen',
    borderColor: '#10B981',
    gradient: 'linear-gradient(210deg, #10B981, #000)',
    url: 'https://linkedin.com/in/',
  },
  {
    image: 'https://i.pravatar.cc/300?img=3',
    title: 'Morgan Blake',
    subtitle: 'UI/UX Designer',
    handle: '@morganblake',
    borderColor: '#F59E0B',
    gradient: 'linear-gradient(165deg, #F59E0B, #000)',
    url: 'https://dribbble.com/',
  },
  {
    image: 'https://i.pravatar.cc/300?img=16',
    title: 'Casey Park',
    subtitle: 'Data Scientist',
    handle: '@caseypark',
    borderColor: '#EF4444',
    gradient: 'linear-gradient(195deg, #EF4444, #000)',
    url: 'https://kaggle.com/',
  },
  {
    image: 'https://i.pravatar.cc/300?img=25',
    title: 'Sam Kim',
    subtitle: 'Mobile Developer',
    handle: '@thesamkim',
    borderColor: '#8B5CF6',
    gradient: 'linear-gradient(225deg, #8B5CF6, #000)',
    url: 'https://github.com/',
  },
  {
    image: 'https://i.pravatar.cc/300?img=60',
    title: 'Tyler Rodriguez',
    subtitle: 'Cloud Architect',
    handle: '@tylerrod',
    borderColor: '#06B6D4',
    gradient: 'linear-gradient(135deg, #06B6D4, #000)',
    url: 'https://aws.amazon.com/',
  },
];

export const ChromaGrid = ({
  items,
  className = '',
  radius = 300,
  columns = 3,
  rows = 2,
  damping = 0.45,
  fadeOut = 0.6,
  ease = 'power3.out',
}) => {
  const rootRef = useRef(null);
  const spotRef = useRef(null);
  const setX = useRef(null);
  const setY = useRef(null);
  const pos = useRef({ x: 0, y: 0 });

  const data = items?.length ? items : demo;

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;

    // Create the spotlight overlay once
    const spot = document.createElement('div');
    spot.className = 'chroma-spotlight';
    spot.style.setProperty('--r', `${radius}px`);
    root.appendChild(spot);
    spotRef.current = spot;

    // GSAP quickSetter for smooth cursor-following
    setX.current = gsap.quickSetter(spot, '--x', 'px');
    setY.current = gsap.quickSetter(spot, '--y', 'px');

    // Animate cursor position with damping
    const onMove = (e) => {
      const rect = root.getBoundingClientRect();
      const tx = e.clientX - rect.left;
      const ty = e.clientY - rect.top;
      gsap.to(pos.current, {
        x: tx,
        y: ty,
        duration: damping,
        ease,
        onUpdate: () => {
          setX.current(pos.current.x);
          setY.current(pos.current.y);
        },
      });
    };

    const onLeave = () => {
      // Fade out spotlight by moving it far off screen
      gsap.to(spot, {
        opacity: 0,
        duration: fadeOut,
        ease: 'power2.out',
        onComplete: () => {
          spot.style.setProperty('--x', '-9999px');
          spot.style.setProperty('--y', '-9999px');
          gsap.set(spot, { opacity: 1 });
        },
      });
    };

    const onEnter = () => {
      gsap.killTweensOf(spot);
      gsap.set(spot, { opacity: 1 });
    };

    root.addEventListener('mousemove', onMove);
    root.addEventListener('mouseleave', onLeave);
    root.addEventListener('mouseenter', onEnter);

    return () => {
      root.removeEventListener('mousemove', onMove);
      root.removeEventListener('mouseleave', onLeave);
      root.removeEventListener('mouseenter', onEnter);
      if (spot.parentNode) spot.parentNode.removeChild(spot);
    };
  }, [radius, damping, fadeOut, ease]);

  return (
    <div
      ref={rootRef}
      className={`chroma-grid ${className}`}
      style={{ gridTemplateColumns: `repeat(${columns}, 1fr)`, gridTemplateRows: `repeat(${rows}, 1fr)` }}
    >
      {data.map((item, i) => (
        <div
          key={i}
          className="chroma-item"
          style={{ '--item-border': item.borderColor }}
        >
          <a href={item.url} target="_blank" rel="noopener noreferrer">
            <div className="chroma-item__inner">
              {/* Gradient background layer */}
              <div
                className="chroma-item__bg"
                style={{ background: item.gradient }}
              />
              <img
                src={item.image}
                alt={item.title}
                className="chroma-item__avatar"
                loading="lazy"
              />
              <p className="chroma-item__title">{item.title}</p>
              <p className="chroma-item__subtitle">{item.subtitle}</p>
              <p className="chroma-item__handle">{item.handle}</p>
            </div>
          </a>
        </div>
      ))}
    </div>
  );
};

export default ChromaGrid;
