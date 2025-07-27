import pygame
import random
import sys
import time
import math

# --- Game settings ---
TILE_SIZE = 128
GRID_WIDTH, GRID_HEIGHT = 16, 16
SCREEN_WIDTH, SCREEN_HEIGHT = TILE_SIZE * GRID_WIDTH, TILE_SIZE * GRID_HEIGHT
FPS = 60
SKY_ROWS = 4  # Number of rows at the top that are sky

# --- Block types and colors ---
BLOCK_TYPES = [
    ('grass', (34, 177, 76)),      # Green
    ('dirt', (185, 122, 87)),      # Brown
    ('stone', (127, 127, 127)),    # Grey
    ('diamond', (0, 255, 255)),    # Cyan
    ('emerald', (0, 255, 0)),      # Bright green
    ('void', (0, 0, 0)),           # Black (void)
    ('lava', (255, 69, 0)),        # Orange-red (lava)
    ('air', (0, 0, 0)),            # Black (empty)
]
BLOCK_NAME_TO_IDX = {name: i for i, (name, _) in enumerate(BLOCK_TYPES)}
BLOCK_KEYS = ['grass', 'dirt', 'stone', 'diamond', 'emerald']

# --- Generate world ---
level_num = 1

def generate_grid():
    grid = []
    void_chance = min(0.02 + 0.01 * (level_num-1), 0.15)
    lava_chance = min(0.01 + 0.01 * (level_num-1), 0.10)
    for y in range(GRID_HEIGHT):
        row = []
        for x in range(GRID_WIDTH):
            if y < SKY_ROWS:
                row.append(BLOCK_NAME_TO_IDX['air'])  # Sky
            elif y == SKY_ROWS:
                row.append(BLOCK_NAME_TO_IDX['grass'])
            elif y < SKY_ROWS + 3:
                if random.random() < void_chance:
                    row.append(BLOCK_NAME_TO_IDX['void'])
                elif random.random() < lava_chance:
                    row.append(BLOCK_NAME_TO_IDX['lava'])
                else:
                    row.append(BLOCK_NAME_TO_IDX['dirt'])
            elif y < SKY_ROWS + 7:
                ore = None
                if random.random() < 0.04:
                    ore = 'diamond'
                elif random.random() < 0.04:
                    ore = 'emerald'
                if ore:
                    row.append(BLOCK_NAME_TO_IDX[ore])
                elif random.random() < void_chance:
                    row.append(BLOCK_NAME_TO_IDX['void'])
                elif random.random() < lava_chance:
                    row.append(BLOCK_NAME_TO_IDX['lava'])
                else:
                    row.append(BLOCK_NAME_TO_IDX['stone'])
            else:
                if random.random() < void_chance:
                    row.append(BLOCK_NAME_TO_IDX['void'])
                elif random.random() < lava_chance:
                    row.append(BLOCK_NAME_TO_IDX['lava'])
                else:
                    row.append(BLOCK_NAME_TO_IDX['stone'])
        grid.append(row)
    return grid

grid = generate_grid()

# --- Player physics ---
# Find the first air cell above the highest solid block in the starting column
for y in range(GRID_HEIGHT):
    if grid[y][GRID_WIDTH // 2] != BLOCK_NAME_TO_IDX['air']:
        player_x = GRID_WIDTH // 2
        player_y = y - 1
        break
else:
    player_x = GRID_WIDTH // 2
    player_y = 0
player_vy = 0
player_vx = 0
on_ground = True
JUMP_VELOCITY = -1  # About 3 blocks high
GRAVITY = 0.05
MAX_FALL_SPEED = 1
MOVE_SPEED = 0.1

# --- Player ---
player_color = (0, 128, 255)

# --- Pygame setup ---
pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption('Pygame Mining Game')
clock = pygame.time.Clock()

# Load player sprite (Miner.png, 2 frames vertically)
try:
    player_sheet = pygame.image.load('Miner.png').convert_alpha()
    frame_width = player_sheet.get_width()
    frame_height = player_sheet.get_height() // 2
    player_frames = [
        player_sheet.subsurface((0, 0, frame_width, frame_height)),      # Idle
        player_sheet.subsurface((0, frame_height, frame_width, frame_height))  # Mining
    ]
    player_frames = [pygame.transform.scale(f, (TILE_SIZE, TILE_SIZE)) for f in player_frames]
except Exception as e:
    print('Error loading Miner.png:', e)
    player_frames = [None, None]

player_frame_idx = 0
mine_anim_timer = 0
MINE_ANIM_DURATION = 0.2  # seconds

# --- Inventory ---
inventory = {name: 0 for name, _ in BLOCK_TYPES if name != 'air'}

def count_ores(grid):
    diamond = 0
    emerald = 0
    for row in grid:
        for idx in row:
            if BLOCK_TYPES[idx][0] == 'diamond':
                diamond += 1
            elif BLOCK_TYPES[idx][0] == 'emerald':
                emerald += 1
    return diamond, emerald

def reset_level():
    global grid, player_x, player_y, player_vy, player_vx, on_ground, inventory, total_diamond, total_emerald
    grid = generate_grid()
    # Place player on first air cell above highest solid block
    for y in range(GRID_HEIGHT):
        if grid[y][GRID_WIDTH // 2] != BLOCK_NAME_TO_IDX['air']:
            player_x = GRID_WIDTH // 2
            player_y = y - 1
            break
    else:
        player_x = GRID_WIDTH // 2
        player_y = 0
    player_vy = 0
    player_vx = 0
    on_ground = True
    inventory = {name: 0 for name, _ in BLOCK_TYPES if name != 'air'}
    total_diamond, total_emerald = count_ores(grid)

# --- Load player sprite (Miner.png, 3 columns x 4 rows) ---
try:
    miner_sheet = pygame.image.load('Miner.png').convert_alpha()
    frame_width = miner_sheet.get_width() // 3
    frame_height = miner_sheet.get_height() // 4
    # [row][col]: row = direction (0=W, 1=N, 2=E, 3=S), col = 0 stand, 1 dynamic, 2 hack
    miner_frames = [
        [miner_sheet.subsurface((j*frame_width, i*frame_height, frame_width, frame_height))
         for j in range(3)]
        for i in range(4)
    ]
    miner_frames = [[pygame.transform.scale(f, (TILE_SIZE, TILE_SIZE)) for f in row] for row in miner_frames]
except Exception as e:
    print('Error loading Miner.png:', e)
    miner_frames = [[None, None, None] for _ in range(4)]

# --- Animation state ---
walk_anim_timer = 0
walk_anim_interval = 0.2 # seconds per walk frame
walk_anim_frame = 0

# --- Helper: get direction from mouse ---
def get_mouse_direction(player_x, player_y, allow_diagonal=False):
    mx, my = pygame.mouse.get_pos()
    px = player_x * TILE_SIZE + TILE_SIZE // 2
    py = int(player_y * TILE_SIZE) + TILE_SIZE // 2
    dx = mx - px
    dy = my - py
    if allow_diagonal:
        angle = (180 / 3.14159) * (math.atan2(-dy, dx))
        if angle < 0:
            angle += 360
        # 8 directions: W, NW, N, NE, E, SE, S, SW
        if 337.5 <= angle or angle < 22.5:
            return 2  # E
        elif 22.5 <= angle < 67.5:
            return 3  # NE
        elif 67.5 <= angle < 112.5:
            return 1  # N
        elif 112.5 <= angle < 157.5:
            return 0  # NW
        elif 157.5 <= angle < 202.5:
            return 0  # W
        elif 202.5 <= angle < 247.5:
            return 7  # SW
        elif 247.5 <= angle < 292.5:
            return 6  # S
        elif 292.5 <= angle < 337.5:
            return 5  # SE
    else:
        if abs(dx) > abs(dy):
            if dx < 0:
                return 0  # W
            else:
                return 2  # E
        else:
            if dy < 0:
                return 1  # N
            else:
                return 3  # S

# --- Main loop ---
reset_level()
pressed_keys = set()
victory = False
game_over = False
score = 0
message_timer = 0
selected_block = 1  # Default to dirt
player_frame_idx = 0
player_dir = 3  # Default facing S

while True:
    if victory:
        screen.fill((0, 0, 0))
        font = pygame.font.SysFont(None, 72)
        text = font.render('Victory!', True, (0, 255, 0))
        screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, SCREEN_HEIGHT // 2 - text.get_height() // 2))
        pygame.display.flip()
        time.sleep(2)
        reset_level()
        victory = False
        continue
    if game_over:
        screen.fill((0, 0, 0))
        font = pygame.font.SysFont(None, 72)
        text = font.render('Game Over!', True, (255, 0, 0))
        screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, SCREEN_HEIGHT // 2 - text.get_height() // 2 - 40))
        font2 = pygame.font.SysFont(None, 48)
        score_text = font2.render(f'Score: {score}', True, (255, 255, 255))
        screen.blit(score_text, (SCREEN_WIDTH // 2 - score_text.get_width() // 2, SCREEN_HEIGHT // 2 + 40))
        pygame.display.flip()
        time.sleep(2)
        level_num = 1
        reset_level()
        game_over = False
        continue

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        elif event.type == pygame.KEYDOWN:
            pressed_keys.add(event.key)
            if event.key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()
            elif event.key == pygame.K_a:
                player_vx = -MOVE_SPEED
            elif event.key == pygame.K_d:
                player_vx = MOVE_SPEED
            elif event.key in (pygame.K_w, pygame.K_SPACE):
                if on_ground:
                    # Diagonal jump if A/D is pressed
                    mx, my = pygame.mouse.get_pos()
                    px = player_x * TILE_SIZE + TILE_SIZE // 2
                    py = int(player_y * TILE_SIZE) + TILE_SIZE // 2
                    dx = mx - px
                    dy = my - py
                    norm = (dx**2 + dy**2) ** 0.5
                    if norm > 0:
                        dx, dy = dx/norm, dy/norm
                        player_vx = MOVE_SPEED * dx
                        player_vy = JUMP_VELOCITY * abs(dy)
                    else:
                        player_vy = JUMP_VELOCITY
                    on_ground = False
            elif event.key in [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5]:
                selected_block = int(event.key) - pygame.K_1
        elif event.type == pygame.KEYUP:
            if event.key == pygame.K_a or event.key == pygame.K_d:
                player_vx = 0
            if event.key in pressed_keys:
                pressed_keys.remove(event.key)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            dir_idx = get_mouse_direction(player_x, player_y, allow_diagonal=True)
            dx, dy = [(-1,0), (-1,-1), (0,-1), (1,-1), (1,0), (1,1), (0,1), (-1,1)][dir_idx]
            for dist in range(1, 4):
                tx = int(player_x) + dx * dist
                ty = int(player_y) + dy * dist
                if 0 <= tx < GRID_WIDTH and 0 <= ty < GRID_HEIGHT:
                    if event.button == 1:  # Left click: mine
                        block_idx = grid[ty][tx]
                        block_name = BLOCK_TYPES[block_idx][0]
                        if block_name == 'lava':
                            game_over = True
                            score = inventory['diamond'] + 2 * inventory['emerald']
                            break
                        if block_name != 'air' and block_name != 'void':
                            inventory[block_name] += 1
                            grid[ty][tx] = BLOCK_NAME_TO_IDX['air']
                            player_frame_idx = 1
                            mine_anim_timer = MINE_ANIM_DURATION
                            player_dir = dir_idx // 2  # Map to 4-sprite directions
                            break
                        # Lava falls if block below is mined
                        if block_name == 'lava' and ty+1 < GRID_HEIGHT and grid[ty+1][tx] == BLOCK_NAME_TO_IDX['air']:
                            grid[ty+1][tx] = BLOCK_NAME_TO_IDX['lava']
                            grid[ty][tx] = BLOCK_NAME_TO_IDX['air']
                    elif event.button == 3:  # Right click: place
                        block_name = BLOCK_KEYS[selected_block]
                        if inventory[block_name] > 0 and grid[ty][tx] == BLOCK_NAME_TO_IDX['air']:
                            grid[ty][tx] = BLOCK_NAME_TO_IDX[block_name]
                            inventory[block_name] -= 1
                            break

    # Gravity and physics (smooth)
    player_vy += GRAVITY
    if player_vy > MAX_FALL_SPEED:
        player_vy = MAX_FALL_SPEED
    new_x = player_x + player_vx
    new_y = player_y + player_vy
    # Horizontal collision check
    if 0 <= new_x < GRID_WIDTH and grid[int(player_y)][int(new_x)] in [BLOCK_NAME_TO_IDX['air'], BLOCK_NAME_TO_IDX['void']]:
        player_x = new_x
    else:
        player_vx = 0
    # Check for collision with ground
    if new_y >= GRID_HEIGHT:
        game_over = True
        score = inventory['diamond'] + 2 * inventory['emerald']
        continue
    elif int(new_y + 1) < GRID_HEIGHT and grid[int(new_y + 1)][int(player_x)] not in [BLOCK_NAME_TO_IDX['air'], BLOCK_NAME_TO_IDX['void']]:
        new_y = int(new_y)
        player_vy = 0
        on_ground = True
    elif int(new_y) < GRID_HEIGHT and grid[int(new_y)][int(player_x)] == BLOCK_NAME_TO_IDX['lava']:
        game_over = True
        score = inventory['diamond'] + 2 * inventory['emerald']
        continue
    else:
        on_ground = False
    player_y = new_y

    # Check for victory
    if inventory['diamond'] >= total_diamond and inventory['emerald'] >= total_emerald and (total_diamond > 0 or total_emerald > 0):
        victory = True

    # Update mining animation timer
    if mine_anim_timer > 0:
        mine_anim_timer -= clock.get_time() / 1000.0
        if mine_anim_timer <= 0:
            player_frame_idx = 0

    # --- Draw ---
    screen.fill((135, 206, 235))  # Blue sky
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            block_idx = grid[y][x]
            if block_idx == BLOCK_NAME_TO_IDX['air'] and y < SKY_ROWS:
                continue  # Don't draw sky blocks
            color = BLOCK_TYPES[block_idx][1]
            pygame.draw.rect(screen, color, (x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE))
            pygame.draw.rect(screen, (40, 40, 40), (x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE), 1)

    # Draw player
    px = int(player_x * TILE_SIZE)
    py = int(player_y * TILE_SIZE)
    # Determine player direction (row)
    dir_idx = get_mouse_direction(player_x, player_y, allow_diagonal=True) // 2
    # Determine state: idle, walking, jumping, falling, mining
    is_mining = (player_frame_idx == 1 and mine_anim_timer > 0)
    is_jumping = player_vy < 0 and not on_ground
    is_falling = player_vy > 0.1 and not on_ground
    is_walking = abs(player_vx) > 0.01 and on_ground and not is_mining
    # Animate walk
    if is_walking:
        walk_anim_timer += clock.get_time() / 1000.0
        if walk_anim_timer > walk_anim_interval:
            walk_anim_timer = 0
            walk_anim_frame = 1 - walk_anim_frame  # toggle between 0 and 1
    else:
        walk_anim_frame = 0
        walk_anim_timer = 0
    # Select frame
    if is_mining:
        frame = miner_frames[dir_idx][2]  # hack
    elif is_jumping:
        frame = miner_frames[1][1]  # row 1, col 1 (jump up)
    elif is_falling:
        frame = miner_frames[3][1]  # row 3, col 1 (fall down)
    elif is_walking:
        frame = miner_frames[dir_idx][walk_anim_frame]  # stand/walk
    else:
        frame = miner_frames[dir_idx][0]  # stand

    if frame:
        screen.blit(frame, (px, py))
    else:
        pygame.draw.circle(screen, (0, 128, 255), (px + TILE_SIZE // 2, py + TILE_SIZE // 2), TILE_SIZE // 2 - 4)

    # Draw inventory and selected block
    font = pygame.font.SysFont(None, 28)
    inv_text = 'Inventory: ' + ', '.join(f'{k}: {inventory[k]}' for k in BLOCK_KEYS)
    sel_text = f' | Selected: {BLOCK_KEYS[selected_block].capitalize()} | Level: {level_num} | Score: {inventory["diamond"] + 2 * inventory["emerald"]}'
    text_surf = font.render(inv_text + sel_text, True, (255, 255, 255))
    screen.blit(text_surf, (10, SCREEN_HEIGHT - 30))

    if victory:
        font = pygame.font.SysFont(None, 72)
        text = font.render(f'Level {level_num} Complete!', True, (0, 255, 0))
        screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, SCREEN_HEIGHT // 2 - text.get_height() // 2 - 40))
        font2 = pygame.font.SysFont(None, 48)
        score_text = font2.render(f'Score: {inventory["diamond"] + 2 * inventory["emerald"]}', True, (255, 255, 255))
        inv_text2 = font2.render(f'Inventory: {inventory}', True, (255, 255, 255))
        screen.blit(score_text, (SCREEN_WIDTH // 2 - score_text.get_width() // 2, SCREEN_HEIGHT // 2 + 40))
        screen.blit(inv_text2, (SCREEN_WIDTH // 2 - inv_text2.get_width() // 2, SCREEN_HEIGHT // 2 + 90))
        pygame.display.flip()
        time.sleep(2)
        level_num += 1
        reset_level()
        victory = False
        continue
    if game_over:
        font = pygame.font.SysFont(None, 72)
        text = font.render('Game Over!', True, (255, 0, 0))
        screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, SCREEN_HEIGHT // 2 - text.get_height() // 2 - 40))
        font2 = pygame.font.SysFont(None, 48)
        score_text = font2.render(f'Score: {score}', True, (255, 255, 255))
        screen.blit(score_text, (SCREEN_WIDTH // 2 - score_text.get_width() // 2, SCREEN_HEIGHT // 2 + 40))
        pygame.display.flip()
        time.sleep(2)
        level_num = 1
        reset_level()
        game_over = False
        continue

    pygame.display.flip()
    clock.tick(FPS)
