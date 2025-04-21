<template>
  <component :is="href ? 'a' : 'button'" v-bind="props" class="button" :class="color">
    {{label}}
  </component>
</template>

<script setup lang="ts">
const props = defineProps<{
  href?: string;
  type?: 'submit' | 'button';
  label: string;
  color?: 'primary' | 'secondary' | 'neutral' | 'danger';
}>();

const {color = 'primary'} = props;
</script>

<style lang="scss" scoped>
.button {
  text-decoration: none;
  font-family: 'Inter', Arial, sans-serif;
  letter-spacing: 0.1em;
  border: none;
  padding: 0.75rem 1rem;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  cursor: pointer;
  text-transform: uppercase;
  background: var(--primary-color);
  color: var(--button-text);

  &.secondary {
    background: var(--secondary-color);
  }

  &.neutral {
    background: var(--neutral-color);
    color: #ffffff;
  }

  &.danger {
    background: var(--danger-color);
  }
}
</style>